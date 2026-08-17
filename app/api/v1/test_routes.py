# from fastapi import APIRouter, UploadFile, File, Depends
# from fastapi.responses import JSONResponse
# from app.services.document_service import DocumentService
# from app.models.responses import UploadResponse
# from app.core.exceptions import SensoryPlatformException
# from app.core.logger import logger

# router = APIRouter(prefix="/documents", tags=["Documents"])

# def get_document_service() -> DocumentService:
#     """Dependency injection for the DocumentService."""
#     return DocumentService()

# @router.post("/upload", response_model=UploadResponse, status_code=201)
# async def upload_document(
#     file: UploadFile = File(..., description="The raw PDF document to upload"),
#     service: DocumentService = Depends(get_document_service)
# ):
#     """
#     Uploads a PDF document to the platform.
#     Creates an isolated storage workspace, checks integrity, and prepares it for the pipeline.
#     """
#     logger.info(f"Incoming upload request for file: {file.filename}")
    
#     try:
#         document_metadata = await service.process_upload(file)
        
#         return UploadResponse(
#             success=True,
#             message="Document uploaded successfully.",
#             data=document_metadata
#         )
        
#     except SensoryPlatformException as e:
#         # Expected business logic errors (e.g., file too large, invalid type)
#         logger.warning(f"Upload failed ({e.status_code}): {e.message}")
#         return JSONResponse(
#             status_code=e.status_code,
#             content={"success": False, "message": e.message}
#         )
        
#     except Exception as e:
#         # Unhandled system failures
#         logger.error(f"Unexpected upload error: {str(e)}", exc_info=True)
#         return JSONResponse(
#             status_code=500,
#             content={"success": False, "message": "An unexpected internal server error occurred."}
#         )






# import json
# from pathlib import Path
# from fastapi import APIRouter, UploadFile, File, Depends, Path as FastAPIPath
# from fastapi.responses import JSONResponse
# from app.services.document_service import DocumentService
# from app.services.processing_service import ProcessingService
# from app.models.responses import UploadResponse
# from app.core.exceptions import SensoryPlatformException, DocumentNotFoundError
# from app.core.logger import logger
# from app.core.config import settings

# router = APIRouter(prefix="/documents", tags=["Documents"])

# def get_document_service() -> DocumentService:
#     return DocumentService()

# def get_processing_service() -> ProcessingService:
#     return ProcessingService()

# @router.post("/upload", response_model=UploadResponse, status_code=201)
# async def upload_document(
#     file: UploadFile = File(..., description="The raw PDF document to upload"),
#     service: DocumentService = Depends(get_document_service)
# ):
#     """Uploads a PDF document to the platform."""
#     logger.info(f"Incoming upload request for file: {file.filename}")
#     try:
#         document_metadata = await service.process_upload(file)
#         return UploadResponse(
#             success=True,
#             message="Document uploaded successfully.",
#             data=document_metadata
#         )
#     except SensoryPlatformException as e:
#         logger.warning(f"Upload failed ({e.status_code}): {e.message}")
#         return JSONResponse(
#             status_code=e.status_code,
#             content={"success": False, "message": e.message}
#         )
#     except Exception as e:
#         logger.error(f"Unexpected upload error: {str(e)}", exc_info=True)
#         return JSONResponse(
#             status_code=500,
#             content={"success": False, "message": "An unexpected internal server error occurred."}
#         )

# @router.post("/{document_id}/process", status_code=200)
# async def process_document(
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: ProcessingService = Depends(get_processing_service)
# ):
#     """Triggers page extraction, image harvesting, and document tree generation."""
#     logger.info(f"Triggering processing for document ID: {document_id}")
#     try:
#         result = await service.process_document(document_id)
#         return {
#             "success": True,
#             "message": "Document processed successfully.",
#             "data": result
#         }
#     except SensoryPlatformException as e:
#         logger.warning(f"Processing failed ({e.status_code}): {e.message}")
#         return JSONResponse(
#             status_code=e.status_code,
#             content={"success": False, "message": e.message}
#         )
#     except Exception as e:
#         logger.error(f"Unexpected processing error: {str(e)}", exc_info=True)
#         return JSONResponse(
#             status_code=500,
#             content={"success": False, "message": "An unexpected internal server error occurred."}
#         )

# @router.get("/{document_id}/tree", status_code=200)
# async def get_document_tree(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the generated document_tree.json artifact for a processed document."""
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
    
#     if not tree_path.exists():
#         raise DocumentNotFoundError(document_id)
        
#     try:
#         with open(tree_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {
#             "success": True,
#             "data": data
#         }
#     except Exception as e:
#         logger.error(f"Failed to read document tree for {document_id}: {str(e)}")
#         return JSONResponse(
#             status_code=500,
#             content={"success": False, "message": "Failed to read document tree artifact."}
#         )







# import json
# from pathlib import Path
# from fastapi import APIRouter, UploadFile, File, Depends, Query, Path as FastAPIPath
# from fastapi.responses import JSONResponse
# from app.services.document_service import DocumentService
# from app.services.processing_service import ProcessingService
# from app.services.knowledge_service import KnowledgeService
# from app.models.responses import UploadResponse
# from app.core.exceptions import SensoryPlatformException, DocumentNotFoundError
# from app.core.logger import logger
# from app.core.config import settings

# router = APIRouter(prefix="/documents", tags=["Documents"])

# def get_document_service() -> DocumentService:
#     return DocumentService()

# def get_processing_service() -> ProcessingService:
#     return ProcessingService()

# def get_knowledge_service() -> KnowledgeService:
#     return KnowledgeService()

# @router.post("/upload", response_model=UploadResponse, status_code=201)
# async def upload_document(
#     file: UploadFile = File(..., description="The raw PDF document to upload"),
#     service: DocumentService = Depends(get_document_service)
# ):
#     """Uploads a PDF document to the platform."""
#     logger.info(f"Incoming upload request for file: {file.filename}")
#     try:
#         document_metadata = await service.process_upload(file)
#         return UploadResponse(
#             success=True,
#             message="Document uploaded successfully.",
#             data=document_metadata
#         )
#     except SensoryPlatformException as e:
#         logger.warning(f"Upload failed ({e.status_code}): {e.message}")
#         return JSONResponse(
#             status_code=e.status_code,
#             content={"success": False, "message": e.message}
#         )
#     except Exception as e:
#         logger.error(f"Unexpected upload error: {str(e)}", exc_info=True)
#         return JSONResponse(
#             status_code=500,
#             content={"success": False, "message": "An unexpected internal server error occurred."}
#         )

# @router.post("/{document_id}/process", status_code=200)
# async def process_document(
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: ProcessingService = Depends(get_processing_service)
# ):
#     """Triggers page extraction, image harvesting, and document tree generation."""
#     logger.info(f"Triggering processing for document ID: {document_id}")
#     try:
#         result = await service.process_document(document_id)
#         return {
#             "success": True,
#             "message": "Document processed successfully.",
#             "data": result
#         }
#     except SensoryPlatformException as e:
#         logger.warning(f"Processing failed ({e.status_code}): {e.message}")
#         return JSONResponse(
#             status_code=e.status_code,
#             content={"success": False, "message": e.message}
#         )
#     except Exception as e:
#         logger.error(f"Unexpected processing error: {str(e)}", exc_info=True)
#         return JSONResponse(
#             status_code=500,
#             content={"success": False, "message": "An unexpected internal server error occurred."}
#         )

# @router.get("/{document_id}/tree", status_code=200)
# async def get_document_tree(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the generated document_tree.json artifact for a processed document."""
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
    
#     if not tree_path.exists():
#         raise DocumentNotFoundError(document_id)
        
#     try:
#         with open(tree_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {
#             "success": True,
#             "data": data
#         }
#     except Exception as e:
#         logger.error(f"Failed to read document tree for {document_id}: {str(e)}")
#         return JSONResponse(
#             status_code=500,
#             content={"success": False, "message": "Failed to read document tree artifact."}
#         )

# @router.post("/{document_id}/extract-knowledge", status_code=200)
# async def extract_knowledge(
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     chunk_size: int = Query(1000, description="Character chunk size"),
#     overlap: int = Query(150, description="Character overlap between chunks"),
#     service: KnowledgeService = Depends(get_knowledge_service)
# ):
#     """Triggers semantic chunking on the extracted page content."""
#     logger.info(f"Triggering knowledge extraction for document ID: {document_id}")
#     try:
#         result = await service.extract_knowledge(document_id, chunk_size=chunk_size, overlap=overlap)
#         return {
#             "success": True,
#             "message": "Knowledge extraction completed successfully.",
#             "data": result
#         }
#     except SensoryPlatformException as e:
#         logger.warning(f"Knowledge extraction failed ({e.status_code}): {e.message}")
#         return JSONResponse(
#             status_code=e.status_code,
#             content={"success": False, "message": e.message}
#         )
#     except Exception as e:
#         logger.error(f"Unexpected knowledge extraction error: {str(e)}", exc_info=True)
#         return JSONResponse(
#             status_code=500,
#             content={"success": False, "message": "An unexpected internal server error occurred."}
#         )

# @router.get("/{document_id}/knowledge", status_code=200)
# async def get_extracted_knowledge(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the extracted_knowledge.json chunk payload for a document."""
#     knowledge_path = settings.STORAGE_PROCESSED_DIR / document_id / "extracted_knowledge.json"
    
#     if not knowledge_path.exists():
#         raise DocumentNotFoundError(document_id)
        
#     try:
#         with open(knowledge_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {
#             "success": True,
#             "data": data
#         }
#     except Exception as e:
#         logger.error(f"Failed to read extracted knowledge for {document_id}: {str(e)}")
#         return JSONResponse(
#             status_code=500,
#             content={"success": False, "message": "Failed to read extracted knowledge artifact."}
#         )









# import json
# from pathlib import Path
# from fastapi import APIRouter, UploadFile, File, Depends, Path as FastAPIPath
# from fastapi.responses import JSONResponse
# from app.services.document_service import DocumentService
# from app.services.processing_service import ProcessingService
# from app.services.structure_service import StructureService
# from app.models.responses import UploadResponse
# from app.core.exceptions import SensoryPlatformException, DocumentNotFoundError
# from app.core.logger import logger
# from app.core.config import settings

# router = APIRouter(prefix="/documents", tags=["Documents"])

# def get_document_service() -> DocumentService:
#     return DocumentService()

# def get_processing_service() -> ProcessingService:
#     return ProcessingService()

# def get_structure_service() -> StructureService:
#     return StructureService()

# @router.post("/upload", response_model=UploadResponse, status_code=201)
# async def upload_document(
#     file: UploadFile = File(..., description="The raw PDF document to upload"),
#     service: DocumentService = Depends(get_document_service)
# ):
#     """Uploads a PDF document to the platform."""
#     logger.info(f"Incoming upload request for file: {file.filename}")
#     try:
#         document_metadata = await service.process_upload(file)
#         return UploadResponse(
#             success=True,
#             message="Document uploaded successfully.",
#             data=document_metadata
#         )
#     except SensoryPlatformException as e:
#         logger.warning(f"Upload failed ({e.status_code}): {e.message}")
#         return JSONResponse(
#             status_code=e.status_code,
#             content={"success": False, "message": e.message}
#         )
#     except Exception as e:
#         logger.error(f"Unexpected upload error: {str(e)}", exc_info=True)
#         return JSONResponse(
#             status_code=500,
#             content={"success": False, "message": "An unexpected internal server error occurred."}
#         )

# @router.post("/{document_id}/process", status_code=200)
# async def process_document(
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: ProcessingService = Depends(get_processing_service)
# ):
#     """Triggers page extraction, image harvesting, and base workspace setup."""
#     logger.info(f"Triggering processing for document ID: {document_id}")
#     try:
#         result = await service.process_document(document_id)
#         return {
#             "success": True,
#             "message": "Document processed successfully.",
#             "data": result
#         }
#     except SensoryPlatformException as e:
#         logger.warning(f"Processing failed ({e.status_code}): {e.message}")
#         return JSONResponse(
#             status_code=e.status_code,
#             content={"success": False, "message": e.message}
#         )
#     except Exception as e:
#         logger.error(f"Unexpected processing error: {str(e)}", exc_info=True)
#         return JSONResponse(
#             status_code=500,
#             content={"success": False, "message": "An unexpected internal server error occurred."}
#         )

# @router.post("/{document_id}/extract-structure", status_code=200)
# async def extract_structure(
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: StructureService = Depends(get_structure_service)
# ):
#     """Extracts Table of Contents, page structures, headings, and layout blocks accurately without chunking."""
#     logger.info(f"Triggering structural extraction for document ID: {document_id}")
#     try:
#         result = await service.build_structural_tree(document_id)
#         return {
#             "success": True,
#             "message": "Document structure extracted successfully.",
#             "data": result
#         }
#     except SensoryPlatformException as e:
#         logger.warning(f"Structure extraction failed ({e.status_code}): {e.message}")
#         return JSONResponse(
#             status_code=e.status_code,
#             content={"success": False, "message": e.message}
#         )
#     except Exception as e:
#         logger.error(f"Unexpected structure extraction error: {str(e)}", exc_info=True)
#         return JSONResponse(
#             status_code=500,
#             content={"success": False, "message": "An unexpected internal server error occurred."}
#         )

# @router.get("/{document_id}/structure", status_code=200)
# async def get_document_structure(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the complete document_tree.json containing structural hierarchy, TOC, and classified text elements."""
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
    
#     if not tree_path.exists():
#         raise DocumentNotFoundError(document_id)
        
#     try:
#         with open(tree_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {
#             "success": True,
#             "data": data
#         }
#     except Exception as e:
#         logger.error(f"Failed to read structural tree for {document_id}: {str(e)}")
#         return JSONResponse(
#             status_code=500,
#             content={"success": False, "message": "Failed to read document tree artifact."}
#         )




    



# import json
# from pathlib import Path
# from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, Path as FastAPIPath
# from fastapi.responses import JSONResponse

# from app.services.document_service import DocumentService
# from app.services.processing_service import ProcessingService
# from app.services.structure_service import StructureService
# from app.services.extraction_service import ExtractionService
# from app.models.responses import UploadResponse
# from app.core.exceptions import SensoryPlatformException, DocumentNotFoundError
# from app.core.logger import logger
# from app.core.config import settings

# router = APIRouter(prefix="/documents", tags=["Documents"])

# def get_document_service() -> DocumentService:
#     return DocumentService()

# def get_processing_service() -> ProcessingService:
#     return ProcessingService()

# def get_structure_service() -> StructureService:
#     return StructureService()

# def get_extraction_service() -> ExtractionService:
#     return ExtractionService()


# @router.post("/upload", response_model=UploadResponse, status_code=201)
# async def upload_document(
#     file: UploadFile = File(..., description="The raw PDF document to upload"),
#     service: DocumentService = Depends(get_document_service)
# ):
#     """Uploads a PDF document to the platform."""
#     logger.info(f"Incoming upload request for file: {file.filename}")
#     try:
#         document_metadata = await service.process_upload(file)
#         return UploadResponse(
#             success=True,
#             message="Document uploaded successfully.",
#             data=document_metadata
#         )
#     except SensoryPlatformException as e:
#         logger.warning(f"Upload failed ({e.status_code}): {e.message}")
#         return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
#     except Exception as e:
#         logger.error(f"Unexpected upload error: {str(e)}", exc_info=True)
#         return JSONResponse(status_code=500, content={"success": False, "message": "An unexpected internal server error occurred."})


# @router.post("/{document_id}/process", status_code=200)
# async def process_document(
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: ProcessingService = Depends(get_processing_service)
# ):
#     """Triggers page extraction, image harvesting, and base workspace setup."""
#     logger.info(f"Triggering processing for document ID: {document_id}")
#     try:
#         result = await service.process_document(document_id)
#         return {"success": True, "message": "Document processed successfully.", "data": result}
#     except SensoryPlatformException as e:
#         return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": str(e)})


# @router.post("/{document_id}/extract-structure", status_code=200)
# async def extract_structure(
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: StructureService = Depends(get_structure_service)
# ):
#     """Extracts Table of Contents, page structures, headings, images, and tables accurately."""
#     logger.info(f"Triggering structural extraction for document ID: {document_id}")
#     try:
#         result = await service.build_structural_tree(document_id)
#         return {"success": True, "message": "Document structure extracted successfully.", "data": result}
#     except SensoryPlatformException as e:
#         return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": str(e)})


# @router.get("/{document_id}/structure", status_code=200)
# async def get_document_structure(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the complete document_tree.json containing structural hierarchy."""
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
    
#     if not tree_path.exists():
#         raise DocumentNotFoundError(document_id)
        
#     try:
#         with open(tree_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {"success": True, "data": data}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to read structure artifact."})


# @router.post("/{document_id}/extract-knowledge", status_code=202)
# async def extract_knowledge(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: ExtractionService = Depends(get_extraction_service)
# ):
#     """Triggers LLM knowledge extraction in the background using OpenAI Structured Outputs."""
#     logger.info(f"Queueing LLM knowledge extraction for document ID: {document_id}")
    
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
#     if not tree_path.exists():
#         return JSONResponse(
#             status_code=400, 
#             content={"success": False, "message": "Structure tree missing. Run /extract-structure first."}
#         )

#     try:
#         # Run the heavy OpenAI loop in the background
#         background_tasks.add_task(service.extract_knowledge, document_id)
        
#         return JSONResponse(
#             status_code=202,
#             content={
#                 "success": True,
#                 "message": "LLM knowledge extraction started in the background.",
#                 "data": {
#                     "document_id": document_id,
#                     "pipeline_status": "EXTRACTING_KNOWLEDGE",
#                     "status_check": f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
#                 }
#             }
#         )
#     except Exception as e:
#         logger.error(f"Failed to start extraction: {str(e)}")
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to start extraction."})


# @router.get("/{document_id}/knowledge", status_code=200)
# async def get_extracted_knowledge(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the extracted_knowledge.json payload containing Pydantic-validated LLM results."""
#     knowledge_path = settings.STORAGE_PROCESSED_DIR / document_id / "extracted_knowledge.json"
    
#     if not knowledge_path.exists():
#         return JSONResponse(
#             status_code=202, 
#             content={"success": True, "message": "Knowledge extraction is still processing or hasn't started.", "data": None}
#         )
        
#     try:
#         with open(knowledge_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {"success": True, "data": data}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to read knowledge artifact."})








# import json
# from pathlib import Path
# from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, Path as FastAPIPath
# from fastapi.responses import JSONResponse

# from app.services.document_service import DocumentService
# from app.services.processing_service import ProcessingService
# from app.services.structure_service import StructureService
# from app.services.extraction_service import ExtractionService
# from app.services.canonical_service import CanonicalService
# from app.models.responses import UploadResponse
# from app.core.exceptions import SensoryPlatformException, DocumentNotFoundError
# from app.core.logger import logger
# from app.core.config import settings

# router = APIRouter(prefix="/documents", tags=["Documents"])

# # --- Dependency Injections ---

# def get_document_service() -> DocumentService:
#     return DocumentService()

# def get_processing_service() -> ProcessingService:
#     return ProcessingService()

# def get_structure_service() -> StructureService:
#     return StructureService()

# def get_extraction_service() -> ExtractionService:
#     return ExtractionService()

# def get_canonical_service() -> CanonicalService:
#     return CanonicalService()

# # --- Upload & Pre-Processing ---

# @router.post("/upload", response_model=UploadResponse, status_code=201)
# async def upload_document(
#     file: UploadFile = File(..., description="The raw PDF document to upload"),
#     service: DocumentService = Depends(get_document_service)
# ):
#     """Uploads a PDF document to the platform."""
#     logger.info(f"Incoming upload request for file: {file.filename}")
#     try:
#         document_metadata = await service.process_upload(file)
#         return UploadResponse(success=True, message="Document uploaded successfully.", data=document_metadata)
#     except SensoryPlatformException as e:
#         logger.warning(f"Upload failed ({e.status_code}): {e.message}")
#         return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
#     except Exception as e:
#         logger.error(f"Unexpected upload error: {str(e)}", exc_info=True)
#         return JSONResponse(status_code=500, content={"success": False, "message": "An unexpected internal server error occurred."})

# @router.post("/{document_id}/process", status_code=200)
# async def process_document(
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: ProcessingService = Depends(get_processing_service)
# ):
#     """Triggers page extraction, image harvesting, and base workspace setup."""
#     logger.info(f"Triggering processing for document ID: {document_id}")
#     try:
#         result = await service.process_document(document_id)
#         return {"success": True, "message": "Document processed successfully.", "data": result}
#     except SensoryPlatformException as e:
#         return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

# # --- Structure Extraction ---

# @router.post("/{document_id}/extract-structure", status_code=200)
# async def extract_structure(
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: StructureService = Depends(get_structure_service)
# ):
#     """Extracts Table of Contents, page structures, headings, images, and tables accurately."""
#     logger.info(f"Triggering structural extraction for document ID: {document_id}")
#     try:
#         result = await service.build_structural_tree(document_id)
#         return {"success": True, "message": "Document structure extracted successfully.", "data": result}
#     except SensoryPlatformException as e:
#         return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

# @router.get("/{document_id}/structure", status_code=200)
# async def get_document_structure(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the complete document_tree.json containing structural hierarchy."""
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
#     if not tree_path.exists():
#         raise DocumentNotFoundError(document_id)
#     try:
#         with open(tree_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {"success": True, "data": data}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to read structure artifact."})

# # --- LLM Knowledge Extraction ---

# @router.post("/{document_id}/extract-knowledge", status_code=202)
# async def extract_knowledge(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: ExtractionService = Depends(get_extraction_service)
# ):
#     """Triggers LLM knowledge extraction in the background using OpenAI Structured Outputs."""
#     logger.info(f"Queueing LLM knowledge extraction for document ID: {document_id}")
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
    
#     if not tree_path.exists():
#         return JSONResponse(
#             status_code=400, 
#             content={"success": False, "message": "Structure tree missing. Run /extract-structure first."}
#         )

#     try:
#         background_tasks.add_task(service.extract_knowledge, document_id)
#         return JSONResponse(
#             status_code=202,
#             content={
#                 "success": True,
#                 "message": "LLM knowledge extraction started in the background.",
#                 "data": {
#                     "document_id": document_id,
#                     "pipeline_status": "EXTRACTING_KNOWLEDGE",
#                     "status_check": f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
#                 }
#             }
#         )
#     except Exception as e:
#         logger.error(f"Failed to start extraction: {str(e)}")
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to start extraction."})

# @router.get("/{document_id}/knowledge", status_code=200)
# async def get_extracted_knowledge(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the extracted_knowledge.json payload containing Pydantic-validated LLM results."""
#     knowledge_path = settings.STORAGE_PROCESSED_DIR / document_id / "extracted_knowledge.json"
#     if not knowledge_path.exists():
#         return JSONResponse(
#             status_code=202, 
#             content={"success": True, "message": "Knowledge extraction is still processing or hasn't started.", "data": None}
#         )
#     try:
#         with open(knowledge_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {"success": True, "data": data}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to read knowledge artifact."})

# # --- Canonical Normalization (Qdrant Sync) ---

# @router.post("/{document_id}/extract-normalize", status_code=202)
# async def extract_normalize(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: CanonicalService = Depends(get_canonical_service)
# ):
#     """Triggers Qdrant Semantic Search to map new concepts to existing Database UIDs."""
#     logger.info(f"Queueing Canonical Normalization for document ID: {document_id}")
#     knowledge_path = settings.STORAGE_PROCESSED_DIR / document_id / "extracted_knowledge.json"
    
#     if not knowledge_path.exists():
#         return JSONResponse(
#             status_code=400, 
#             content={"success": False, "message": "Extracted knowledge missing. Run /extract-knowledge first."}
#         )

#     try:
#         background_tasks.add_task(service.normalize_concepts, document_id)
#         return JSONResponse(
#             status_code=202,
#             content={
#                 "success": True,
#                 "message": "Canonical Normalization started in the background.",
#                 "data": {
#                     "document_id": document_id,
#                     "pipeline_status": "NORMALIZING",
#                     "status_check": f"{settings.API_V1_STR}/documents/{document_id}/normalize"
#                 }
#             }
#         )
#     except Exception as e:
#         logger.error(f"Failed to start normalization: {str(e)}")
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to start normalization."})

# @router.get("/{document_id}/normalize", status_code=200)
# async def get_normalized_concepts(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the canonical_mapping.json payload with matched UIDs and New Proposals."""
#     mapping_path = settings.STORAGE_PROCESSED_DIR / document_id / "canonical_mapping.json"
#     if not mapping_path.exists():
#         return JSONResponse(
#             status_code=202, 
#             content={"success": True, "message": "Canonical normalization is still processing or hasn't started.", "data": None}
#         )
#     try:
#         with open(mapping_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {"success": True, "data": data}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to read normalization artifact."})

    






# import json
# from pathlib import Path
# from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, Path as FastAPIPath
# from fastapi.responses import JSONResponse

# from app.services.document_service import DocumentService
# from app.services.processing_service import ProcessingService
# from app.services.structure_service import StructureService
# from app.services.extraction_service import ExtractionService
# from app.services.canonical_service import CanonicalService
# from app.services.schema_service import SchemaService
# from app.models.responses import UploadResponse
# from app.core.exceptions import SensoryPlatformException, DocumentNotFoundError
# from app.core.logger import logger
# from app.core.config import settings

# router = APIRouter(prefix="/documents", tags=["Documents"])

# # --- Dependency Injections ---

# def get_document_service() -> DocumentService:
#     return DocumentService()

# def get_processing_service() -> ProcessingService:
#     return ProcessingService()

# def get_structure_service() -> StructureService:
#     return StructureService()

# def get_extraction_service() -> ExtractionService:
#     return ExtractionService()

# def get_canonical_service() -> CanonicalService:
#     return CanonicalService()

# def get_schema_service() -> SchemaService:
#     return SchemaService()

# # --- Upload & Pre-Processing ---

# @router.post("/upload", response_model=UploadResponse, status_code=201)
# async def upload_document(
#     file: UploadFile = File(..., description="The raw PDF document to upload"),
#     service: DocumentService = Depends(get_document_service)
# ):
#     """Uploads a PDF document to the platform."""
#     logger.info(f"Incoming upload request for file: {file.filename}")
#     try:
#         document_metadata = await service.process_upload(file)
#         return UploadResponse(success=True, message="Document uploaded successfully.", data=document_metadata)
#     except SensoryPlatformException as e:
#         logger.warning(f"Upload failed ({e.status_code}): {e.message}")
#         return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
#     except Exception as e:
#         logger.error(f"Unexpected upload error: {str(e)}", exc_info=True)
#         return JSONResponse(status_code=500, content={"success": False, "message": "An unexpected internal server error occurred."})

# @router.post("/{document_id}/process", status_code=200)
# async def process_document(
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: ProcessingService = Depends(get_processing_service)
# ):
#     """Triggers page extraction, image harvesting, and base workspace setup."""
#     logger.info(f"Triggering processing for document ID: {document_id}")
#     try:
#         result = await service.process_document(document_id)
#         return {"success": True, "message": "Document processed successfully.", "data": result}
#     except SensoryPlatformException as e:
#         return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

# # --- Structure Extraction ---

# @router.post("/{document_id}/extract-structure", status_code=200)
# async def extract_structure(
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: StructureService = Depends(get_structure_service)
# ):
#     """Extracts Table of Contents, page structures, headings, images, and tables accurately."""
#     logger.info(f"Triggering structural extraction for document ID: {document_id}")
#     try:
#         result = await service.build_structural_tree(document_id)
#         return {"success": True, "message": "Document structure extracted successfully.", "data": result}
#     except SensoryPlatformException as e:
#         return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

# @router.get("/{document_id}/structure", status_code=200)
# async def get_document_structure(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the complete document_tree.json containing structural hierarchy."""
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
#     if not tree_path.exists():
#         raise DocumentNotFoundError(document_id)
#     try:
#         with open(tree_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {"success": True, "data": data}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to read structure artifact."})

# # --- LLM Knowledge Extraction ---

# @router.post("/{document_id}/extract-knowledge", status_code=202)
# async def extract_knowledge(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: ExtractionService = Depends(get_extraction_service)
# ):
#     """Triggers LLM knowledge extraction in the background using OpenAI Structured Outputs."""
#     logger.info(f"Queueing LLM knowledge extraction for document ID: {document_id}")
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
    
#     if not tree_path.exists():
#         return JSONResponse(
#             status_code=400, 
#             content={"success": False, "message": "Structure tree missing. Run /extract-structure first."}
#         )

#     try:
#         background_tasks.add_task(service.extract_knowledge, document_id)
#         return JSONResponse(
#             status_code=202,
#             content={
#                 "success": True,
#                 "message": "LLM knowledge extraction started in the background.",
#                 "data": {
#                     "document_id": document_id,
#                     "pipeline_status": "EXTRACTING_KNOWLEDGE",
#                     "status_check": f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
#                 }
#             }
#         )
#     except Exception as e:
#         logger.error(f"Failed to start extraction: {str(e)}")
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to start extraction."})

# @router.get("/{document_id}/knowledge", status_code=200)
# async def get_extracted_knowledge(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the extracted_knowledge.json payload containing Pydantic-validated LLM results."""
#     knowledge_path = settings.STORAGE_PROCESSED_DIR / document_id / "extracted_knowledge.json"
#     if not knowledge_path.exists():
#         return JSONResponse(
#             status_code=202, 
#             content={"success": True, "message": "Knowledge extraction is still processing or hasn't started.", "data": None}
#         )
#     try:
#         with open(knowledge_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {"success": True, "data": data}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to read knowledge artifact."})

# # --- Canonical Normalization (Qdrant Sync) ---

# @router.post("/{document_id}/extract-normalize", status_code=202)
# async def extract_normalize(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: CanonicalService = Depends(get_canonical_service)
# ):
#     """Triggers Qdrant Semantic Search to map new concepts to existing Database UIDs."""
#     logger.info(f"Queueing Canonical Normalization for document ID: {document_id}")
#     knowledge_path = settings.STORAGE_PROCESSED_DIR / document_id / "extracted_knowledge.json"
    
#     if not knowledge_path.exists():
#         return JSONResponse(
#             status_code=400, 
#             content={"success": False, "message": "Extracted knowledge missing. Run /extract-knowledge first."}
#         )

#     try:
#         background_tasks.add_task(service.normalize_concepts, document_id)
#         return JSONResponse(
#             status_code=202,
#             content={
#                 "success": True,
#                 "message": "Canonical Normalization started in the background.",
#                 "data": {
#                     "document_id": document_id,
#                     "pipeline_status": "NORMALIZING",
#                     "status_check": f"{settings.API_V1_STR}/documents/{document_id}/normalize"
#                 }
#             }
#         )
#     except Exception as e:
#         logger.error(f"Failed to start normalization: {str(e)}")
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to start normalization."})

# @router.get("/{document_id}/normalize", status_code=200)
# async def get_normalized_concepts(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the canonical_mapping.json payload with matched UIDs and New Proposals."""
#     mapping_path = settings.STORAGE_PROCESSED_DIR / document_id / "canonical_mapping.json"
#     if not mapping_path.exists():
#         return JSONResponse(
#             status_code=202, 
#             content={"success": True, "message": "Canonical normalization is still processing or hasn't started.", "data": None}
#         )
#     try:
#         with open(mapping_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {"success": True, "data": data}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to read normalization artifact."})


# # --- Schema Mapper & Graph Validation ---

# @router.post("/{document_id}/map-schema", status_code=202)
# async def map_schema(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: SchemaService = Depends(get_schema_service)
# ):
#     """Triggers the MySQL Schema Mapper and Graph Validation in the background."""
#     logger.info(f"Queueing Schema Mapping for document ID: {document_id}")
#     knowledge_path = settings.STORAGE_PROCESSED_DIR / document_id / "extracted_knowledge.json"
#     mapping_path = settings.STORAGE_PROCESSED_DIR / document_id / "canonical_mapping.json"
    
#     if not knowledge_path.exists() or not mapping_path.exists():
#         return JSONResponse(
#             status_code=400, 
#             content={"success": False, "message": "Prerequisites missing. Run extraction and normalization first."}
#         )

#     try:
#         background_tasks.add_task(service.build_mysql_payload, document_id)
#         return JSONResponse(
#             status_code=202,
#             content={
#                 "success": True,
#                 "message": "Schema mapping started in the background.",
#                 "data": {
#                     "document_id": document_id,
#                     "pipeline_status": "MAPPING_SCHEMA",
#                     "status_check": f"{settings.API_V1_STR}/documents/{document_id}/schema"
#                 }
#             }
#         )
#     except Exception as e:
#         logger.error(f"Failed to start schema mapping: {str(e)}")
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to start schema mapping."})

# @router.get("/{document_id}/schema", status_code=200)
# async def get_mapped_schema(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the mysql_payload.json containing tables ready for DB insertion."""
#     schema_path = settings.STORAGE_PROCESSED_DIR / document_id / "mysql_payload.json"
#     if not schema_path.exists():
#         return JSONResponse(
#             status_code=202, 
#             content={"success": True, "message": "Schema mapping is still processing or hasn't started.", "data": None}
#         )
#     try:
#         with open(schema_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {"success": True, "data": data}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to read schema artifact."})






# import json
# from pathlib import Path
# from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, Path as FastAPIPath
# from fastapi.responses import JSONResponse

# from app.services.document_service import DocumentService
# from app.services.processing_service import ProcessingService
# from app.services.structure_service import StructureService
# from app.services.extraction_service import ExtractionService
# from app.services.canonical_service import CanonicalService
# from app.services.schema_service import SchemaService
# from app.services.mysql_service import MySQLService
# from app.models.responses import UploadResponse
# from app.core.exceptions import SensoryPlatformException, DocumentNotFoundError
# from app.core.logger import logger
# from app.core.config import settings

# router = APIRouter(prefix="/documents", tags=["Documents"])

# # --- Dependency Injections ---

# def get_document_service() -> DocumentService:
#     return DocumentService()

# def get_processing_service() -> ProcessingService:
#     return ProcessingService()

# def get_structure_service() -> StructureService:
#     return StructureService()

# def get_extraction_service() -> ExtractionService:
#     return ExtractionService()

# def get_canonical_service() -> CanonicalService:
#     return CanonicalService()

# def get_schema_service() -> SchemaService:
#     return SchemaService()

# def get_mysql_service() -> MySQLService:
#     return MySQLService()


# # --- Upload & Pre-Processing ---

# @router.post("/upload", response_model=UploadResponse, status_code=201)
# async def upload_document(
#     file: UploadFile = File(..., description="The raw PDF document to upload"),
#     service: DocumentService = Depends(get_document_service)
# ):
#     """Uploads a PDF document to the platform."""
#     logger.info(f"Incoming upload request for file: {file.filename}")
#     try:
#         document_metadata = await service.process_upload(file)
#         return UploadResponse(success=True, message="Document uploaded successfully.", data=document_metadata)
#     except SensoryPlatformException as e:
#         logger.warning(f"Upload failed ({e.status_code}): {e.message}")
#         return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
#     except Exception as e:
#         logger.error(f"Unexpected upload error: {str(e)}", exc_info=True)
#         return JSONResponse(status_code=500, content={"success": False, "message": "An unexpected internal server error occurred."})

# @router.post("/{document_id}/process", status_code=200)
# async def process_document(
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: ProcessingService = Depends(get_processing_service)
# ):
#     """Triggers page extraction, image harvesting, and base workspace setup."""
#     logger.info(f"Triggering processing for document ID: {document_id}")
#     try:
#         result = await service.process_document(document_id)
#         return {"success": True, "message": "Document processed successfully.", "data": result}
#     except SensoryPlatformException as e:
#         return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": str(e)})


# # --- Structure Extraction ---

# @router.post("/{document_id}/extract-structure", status_code=200)
# async def extract_structure(
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: StructureService = Depends(get_structure_service)
# ):
#     """Extracts Table of Contents, page structures, headings, images, and tables accurately."""
#     logger.info(f"Triggering structural extraction for document ID: {document_id}")
#     try:
#         result = await service.build_structural_tree(document_id)
#         return {"success": True, "message": "Document structure extracted successfully.", "data": result}
#     except SensoryPlatformException as e:
#         return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

# @router.get("/{document_id}/structure", status_code=200)
# async def get_document_structure(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the complete document_tree.json containing structural hierarchy."""
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
#     if not tree_path.exists():
#         raise DocumentNotFoundError(document_id)
#     try:
#         with open(tree_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {"success": True, "data": data}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to read structure artifact."})


# # --- LLM Knowledge Extraction ---

# @router.post("/{document_id}/extract-knowledge", status_code=202)
# async def extract_knowledge(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: ExtractionService = Depends(get_extraction_service)
# ):
#     """Triggers LLM knowledge extraction in the background using OpenAI Structured Outputs."""
#     logger.info(f"Queueing LLM knowledge extraction for document ID: {document_id}")
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
    
#     if not tree_path.exists():
#         return JSONResponse(status_code=400, content={"success": False, "message": "Structure tree missing. Run /extract-structure first."})

#     try:
#         background_tasks.add_task(service.extract_knowledge, document_id)
#         return JSONResponse(
#             status_code=202,
#             content={
#                 "success": True,
#                 "message": "LLM knowledge extraction started in the background.",
#                 "data": {
#                     "document_id": document_id,
#                     "pipeline_status": "EXTRACTING_KNOWLEDGE",
#                     "status_check": f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
#                 }
#             }
#         )
#     except Exception as e:
#         logger.error(f"Failed to start extraction: {str(e)}")
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to start extraction."})

# @router.get("/{document_id}/knowledge", status_code=200)
# async def get_extracted_knowledge(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the extracted_knowledge.json payload containing Pydantic-validated LLM results."""
#     knowledge_path = settings.STORAGE_PROCESSED_DIR / document_id / "extracted_knowledge.json"
#     if not knowledge_path.exists():
#         return JSONResponse(status_code=202, content={"success": True, "message": "Knowledge extraction is still processing or hasn't started.", "data": None})
#     try:
#         with open(knowledge_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {"success": True, "data": data}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to read knowledge artifact."})


# # --- Canonical Normalization (Qdrant Sync) ---

# @router.post("/{document_id}/extract-normalize", status_code=202)
# async def extract_normalize(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: CanonicalService = Depends(get_canonical_service)
# ):
#     """Triggers Qdrant Semantic Search to map new concepts to existing Database UIDs."""
#     logger.info(f"Queueing Canonical Normalization for document ID: {document_id}")
#     knowledge_path = settings.STORAGE_PROCESSED_DIR / document_id / "extracted_knowledge.json"
    
#     if not knowledge_path.exists():
#         return JSONResponse(status_code=400, content={"success": False, "message": "Extracted knowledge missing. Run /extract-knowledge first."})

#     try:
#         background_tasks.add_task(service.normalize_concepts, document_id)
#         return JSONResponse(
#             status_code=202,
#             content={
#                 "success": True,
#                 "message": "Canonical Normalization started in the background.",
#                 "data": {
#                     "document_id": document_id,
#                     "pipeline_status": "NORMALIZING",
#                     "status_check": f"{settings.API_V1_STR}/documents/{document_id}/normalize"
#                 }
#             }
#         )
#     except Exception as e:
#         logger.error(f"Failed to start normalization: {str(e)}")
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to start normalization."})

# @router.get("/{document_id}/normalize", status_code=200)
# async def get_normalized_concepts(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the canonical_mapping.json payload with matched UIDs and New Proposals."""
#     mapping_path = settings.STORAGE_PROCESSED_DIR / document_id / "canonical_mapping.json"
#     if not mapping_path.exists():
#         return JSONResponse(status_code=202, content={"success": True, "message": "Canonical normalization is still processing or hasn't started.", "data": None})
#     try:
#         with open(mapping_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {"success": True, "data": data}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to read normalization artifact."})


# # --- Schema Mapper & Graph Validation ---

# @router.post("/{document_id}/map-schema", status_code=202)
# async def map_schema(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: SchemaService = Depends(get_schema_service)
# ):
#     """Triggers the MySQL Schema Mapper and Graph Validation in the background."""
#     logger.info(f"Queueing Schema Mapping for document ID: {document_id}")
#     knowledge_path = settings.STORAGE_PROCESSED_DIR / document_id / "extracted_knowledge.json"
#     mapping_path = settings.STORAGE_PROCESSED_DIR / document_id / "canonical_mapping.json"
    
#     if not knowledge_path.exists() or not mapping_path.exists():
#         return JSONResponse(status_code=400, content={"success": False, "message": "Prerequisites missing. Run extraction and normalization first."})

#     try:
#         background_tasks.add_task(service.build_mysql_payload, document_id)
#         return JSONResponse(
#             status_code=202,
#             content={
#                 "success": True,
#                 "message": "Schema mapping started in the background.",
#                 "data": {
#                     "document_id": document_id,
#                     "pipeline_status": "MAPPING_SCHEMA",
#                     "status_check": f"{settings.API_V1_STR}/documents/{document_id}/schema"
#                 }
#             }
#         )
#     except Exception as e:
#         logger.error(f"Failed to start schema mapping: {str(e)}")
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to start schema mapping."})

# @router.get("/{document_id}/schema", status_code=200)
# async def get_mapped_schema(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the mysql_payload.json containing tables ready for DB insertion."""
#     schema_path = settings.STORAGE_PROCESSED_DIR / document_id / "mysql_payload.json"
#     if not schema_path.exists():
#         return JSONResponse(status_code=202, content={"success": True, "message": "Schema mapping is still processing or hasn't started.", "data": None})
#     try:
#         with open(schema_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {"success": True, "data": data}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to read schema artifact."})


# # --- Final Database Commit ---

# @router.post("/{document_id}/commit", status_code=202)
# async def commit_to_database(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: MySQLService = Depends(get_mysql_service)
# ):
#     """Executes the final MySQL transaction, inserting the validated knowledge graph."""
#     logger.info(f"Queueing MySQL commit for document ID: {document_id}")
#     payload_path = settings.STORAGE_PROCESSED_DIR / document_id / "mysql_payload.json"
    
#     if not payload_path.exists():
#         return JSONResponse(
#             status_code=400, 
#             content={"success": False, "message": "Schema payload missing. Run /map-schema first."}
#         )

#     try:
#         background_tasks.add_task(service.commit_schema_to_db, document_id)
#         return JSONResponse(
#             status_code=202,
#             content={
#                 "success": True,
#                 "message": "Database commit started in the background.",
#                 "data": {
#                     "document_id": document_id,
#                     "pipeline_status": "COMMITTING_TO_DB",
#                     "status_check": f"{settings.API_V1_STR}/documents/{document_id}/status"
#                 }
#             }
#         )
#     except Exception as e:
#         logger.error(f"Failed to start database commit: {str(e)}")
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to start database commit."})

# @router.get("/{document_id}/status", status_code=200)
# async def get_pipeline_status(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Fetches the overall status of the document from metadata.json."""
#     metadata_path = settings.STORAGE_RAW_DIR / document_id / "metadata.json"
#     if not metadata_path.exists():
#         return JSONResponse(status_code=404, content={"success": False, "message": f"Document {document_id} not found."})
#     try:
#         with open(metadata_path, "r", encoding="utf-8") as f:
#             metadata = json.load(f)
#         return {"success": True, "data": metadata}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to retrieve status."})














# import json
# from pathlib import Path
# from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, Path as FastAPIPath
# from fastapi.responses import JSONResponse

# from app.services.document_service import DocumentService
# from app.services.pipeline_orchestrator import PipelineOrchestrator
# from app.services.proposal_service import ProposalService
# from app.services.mysql_service import MySQLService
# from app.models.responses import UploadResponse
# from app.core.exceptions import SensoryPlatformException, DocumentNotFoundError
# from app.core.logger import logger
# from app.core.config import settings
# from app.services.structure_service import StructureService

# router = APIRouter(prefix="/documents", tags=["Documents"])

# def get_document_service() -> DocumentService:
#     return DocumentService()

# def get_proposal_service() -> ProposalService:
#     return ProposalService()

# def get_mysql_service() -> MySQLService:
#     return MySQLService()

# def get_structure_service() -> StructureService:
#     return StructureService()


# # 1. Upload Document
# @router.post("/upload", response_model=UploadResponse, status_code=201)
# async def upload_document(
#     file: UploadFile = File(..., description="Upload PDF, Book, or Research Paper"),
#     service: DocumentService = Depends(get_document_service)
# ):
#     logger.info(f"Incoming upload: {file.filename}")
#     try:
#         metadata = await service.process_upload(file)
#         return UploadResponse(success=True, message="Document uploaded successfully.", data=metadata)
#     except SensoryPlatformException as e:
#         return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
#     except Exception as e:
#         logger.error(f"Upload error: {str(e)}", exc_info=True)
#         return JSONResponse(status_code=500, content={"success": False, "message": "Internal server error."})


# # 2. Process Document (Background Orchestration)
# @router.post("/{document_id}/process", status_code=202)
# async def process_document(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(..., description="Document UUID")
# ):
#     metadata_path = settings.STORAGE_RAW_DIR / document_id / "metadata.json"
#     if not metadata_path.exists():
#         raise DocumentNotFoundError(document_id)

#     orchestrator = PipelineOrchestrator(document_id)
#     background_tasks.add_task(orchestrator.run_full_pipeline)

#     return {
#         "success": True,
#         "message": "Document processing started in the background.",
#         "data": {
#             "document_id": document_id,
#             "status": "RUNNING",
#             "status_endpoint": f"{settings.API_V1_STR}/documents/{document_id}/status"
#         }
#     }


# # 3. Status API
# @router.get("/{document_id}/status", status_code=200)
# async def get_document_status(document_id: str = FastAPIPath(...)):
#     metadata_path = settings.STORAGE_RAW_DIR / document_id / "metadata.json"
#     if not metadata_path.exists():
#         raise DocumentNotFoundError(document_id)

#     with open(metadata_path, "r", encoding="utf-8") as f:
#         meta = json.load(f)

#     return {
#         "success": True,
#         "data": {
#             "document_id": document_id,
#             "status": meta.get("pipeline_status", "UNKNOWN"),
#             "progress": meta.get("progress", 0),
#             "current_stage": meta.get("current_stage", "PENDING"),
#             "completed_stages": meta.get("completed_stages", []),
#             "remaining_stages": meta.get("remaining_stages", [])
#         }
#     }


# # 4. Extracted Artifacts / Extracted Content API
# @router.get("/{document_id}/extracted", status_code=200)
# async def get_extracted_content(document_id: str = FastAPIPath(...)):
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
#     if not tree_path.exists():
#         return JSONResponse(status_code=400, content={"success": False, "message": "Extraction not completed yet."})

#     with open(tree_path, "r", encoding="utf-8") as f:
#         data = json.load(f)
#     return {"success": True, "data": data}



# # --- Structure Extraction ---

# @router.post("/{document_id}/extract-structure", status_code=200)
# async def extract_structure(
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: StructureService = Depends(get_structure_service)
# ):
#     """Extracts Table of Contents, page structures, headings, images, and tables accurately."""
#     logger.info(f"Triggering structural extraction for document ID: {document_id}")
#     try:
#         result = await service.build_structural_tree(document_id)
#         return {"success": True, "message": "Document structure extracted successfully.", "data": result}
#     except SensoryPlatformException as e:
#         return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

# @router.get("/{document_id}/structure", status_code=200)
# async def get_document_structure(
#     document_id: str = FastAPIPath(..., description="The unique document identifier")
# ):
#     """Retrieves the complete document_tree.json containing structural hierarchy."""
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
#     if not tree_path.exists():
#         raise DocumentNotFoundError(document_id)
#     try:
#         with open(tree_path, "r", encoding="utf-8") as f:
#             data = json.load(f)
#         return {"success": True, "data": data}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to read structure artifact."})




# # 5. Document Structure / Tree API
# @router.get("/{document_id}/structure", status_code=200)
# async def get_document_structure(document_id: str = FastAPIPath(...)):
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
#     if not tree_path.exists():
#         raise DocumentNotFoundError(document_id)

#     with open(tree_path, "r", encoding="utf-8") as f:
#         data = json.load(f)
#     return {"success": True, "data": data}


# # # 6. Knowledge API
# # @router.get("/{document_id}/knowledge", status_code=200)
# # async def get_knowledge(document_id: str = FastAPIPath(...)):
# #     knowledge_path = settings.STORAGE_PROCESSED_DIR / document_id / "extracted_knowledge.json"
# #     if not knowledge_path.exists():
# #         return JSONResponse(status_code=400, content={"success": False, "message": "Knowledge extraction pending."})

# #     with open(knowledge_path, "r", encoding="utf-8") as f:
# #         data = json.load(f)
# #     return {"success": True, "data": data}



# # @router.get("/{document_id}/knowledge", status_code=200)
# # async def get_extracted_knowledge(
# #     document_id: str = FastAPIPath(..., description="Unique document identifier")
# # ):
# #     """
# #     Retrieves the extracted knowledge graph containing concepts, 
# #     relationships, rules, and procedures built from unchunked page layouts.
# #     """
# #     knowledge_path = settings.STORAGE_PROCESSED_DIR / document_id / "extracted_knowledge.json"
    
# #     if not knowledge_path.exists():
# #         return JSONResponse(
# #             status_code=202, 
# #             content={
# #                 "success": False, 
# #                 "message": "Knowledge extraction is still processing or hasn't started."
# #             }
# #         )
        
# #     try:
# #         with open(knowledge_path, "r", encoding="utf-8") as f:
# #             data = json.load(f)
            
# #         return {
# #             "success": True,
# #             "data": data
# #         }
# #     except Exception as e:
# #         return JSONResponse(
# #             status_code=500, 
# #             content={"success": False, "message": "Failed to read knowledge artifact."}
# #         )


# # from app.services.extraction_service import ExtractionService

# # def get_extraction_service() -> ExtractionService:
# #     return ExtractionService()

# # @router.post("/{document_id}/extract-knowledge", status_code=202)
# # async def extract_knowledge(
# #     background_tasks: BackgroundTasks,
# #     document_id: str = FastAPIPath(..., description="Unique document identifier"),
# #     service: ExtractionService = Depends(get_extraction_service)
# # ):
# #     """
# #     Takes unchunked page layouts (text, tables, images) and sends them to the LLM 
# #     to build relationship nodes and subnodes. Runs asynchronously in the background.
# #     """
# #     logger.info(f"Queueing unchunked LLM extraction for document: {document_id}")
# #     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
    
# #     if not tree_path.exists():
# #         return JSONResponse(
# #             status_code=400, 
# #             content={"success": False, "message": "Document structure tree missing. Run /extract-structure first."}
# #         )

# #     try:
# #         background_tasks.add_task(service.extract_knowledge, document_id)
# #         return JSONResponse(
# #             status_code=202,
# #             content={
# #                 "success": True,
# #                 "message": "Unchunked LLM extraction started in the background.",
# #                 "data": {
# #                     "document_id": document_id,
# #                     "pipeline_status": "EXTRACTING_KNOWLEDGE",
# #                     "status_check": f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
# #                 }
# #             }
# #         )
# #     except Exception as e:
# #         logger.error(f"Failed to trigger extraction: {str(e)}")
# #         return JSONResponse(status_code=500, content={"success": False, "message": "Failed to start extraction pipeline."})



# from app.services.knowledge_service import KnowledgeService

# def get_knowledge_service() -> KnowledgeService:
#     return KnowledgeService()

# @router.post("/{document_id}/extract-knowledge", status_code=202)
# async def extract_knowledge(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(..., description="Unique document identifier"),
#     service: KnowledgeService = Depends(get_knowledge_service)
# ):
#     """Triggers unchunked LLM extraction to build nodes, subnodes, and relationships in the background."""
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
#     if not tree_path.exists():
#         return JSONResponse(status_code=400, content={"success": False, "message": "Structure tree missing. Run /extract-structure first."})

#     background_tasks.add_task(service.extract_knowledge, document_id)
#     return {
#         "success": True,
#         "message": "Unchunked LLM extraction started in the background.",
#         "data": {
#             "document_id": document_id,
#             "pipeline_status": "EXTRACTING_KNOWLEDGE"
#         }
#     }

# @router.get("/{document_id}/knowledge", status_code=200)
# async def get_extracted_knowledge(document_id: str = FastAPIPath(...)):
#     """Returns the exact unchunked knowledge graph output matching your required schema."""
#     knowledge_path = settings.STORAGE_PROCESSED_DIR / document_id / "extracted_knowledge.json"
#     if not knowledge_path.exists():
#         return JSONResponse(status_code=202, content={"success": True, "message": "Knowledge extraction is still processing.", "data": None})

#     with open(knowledge_path, "r", encoding="utf-8") as f:
#         data = json.load(f)
        
#     return {
#         "success": True,
#         "data": {
#             "document_id": document_id,
#             "concepts": data.get("concepts", []),
#             "relationships": data.get("relationships", []),
#             "scientific_rules": data.get("scientific_rules", []),
#             "procedures": data.get("procedures", [])
#         }
#     }


# # 7. Canonical Mapping API
# @router.get("/{document_id}/canonical", status_code=200)
# async def get_canonical(document_id: str = FastAPIPath(...)):
#     mapping_path = settings.STORAGE_PROCESSED_DIR / document_id / "canonical_mapping.json"
#     if not mapping_path.exists():
#         return JSONResponse(status_code=400, content={"success": False, "message": "Canonical mapping pending."})

#     with open(mapping_path, "r", encoding="utf-8") as f:
#         data = json.load(f)
#     return {"success": True, "data": data}


# # 8. Preview API (Before Insert)
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


# # 9. Commit API (Writes to MySQL Source of Truth)
# @router.post("/{document_id}/commit", status_code=200)
# async def commit_document(
#     document_id: str = FastAPIPath(...),
#     mysql_service: MySQLService = Depends(get_mysql_service)
# ):
#     try:
#         result = await mysql_service.commit_schema_to_db(document_id)
#         return {
#             "success": True,
#             "message": "Committed to MySQL successfully.",
#             "data": result
#         }
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": str(e)})
    



# import json
# from pathlib import Path
# from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, Path as FastAPIPath
# from fastapi.responses import JSONResponse

# from app.services.document_service import DocumentService
# from app.services.pipeline_orchestrator import PipelineOrchestrator
# from app.services.proposal_service import ProposalService
# from app.services.mysql_service import MySQLService
# from app.services.structure_service import StructureService
# from app.services.knowledge_service import KnowledgeService
# from app.models.responses import UploadResponse
# from app.core.exceptions import SensoryPlatformException, DocumentNotFoundError
# from app.core.logger import logger
# from app.core.config import settings

# router = APIRouter(prefix="/documents", tags=["Documents"])

# def get_document_service() -> DocumentService:
#     return DocumentService()

# def get_proposal_service() -> ProposalService:
#     return ProposalService()

# def get_mysql_service() -> MySQLService:
#     return MySQLService()

# def get_structure_service() -> StructureService:
#     return StructureService()

# def get_knowledge_service() -> KnowledgeService:
#     return KnowledgeService()

# # -----------------------------------------------------------------------------
# # 1. UPLOAD
# # -----------------------------------------------------------------------------
# @router.post("/upload", response_model=UploadResponse, status_code=201)
# async def upload_document(
#     file: UploadFile = File(..., description="Upload PDF, Book, or Research Paper"),
#     service: DocumentService = Depends(get_document_service)
# ):
#     logger.info(f"Incoming upload: {file.filename}")
#     try:
#         metadata = await service.process_upload(file)
#         return UploadResponse(success=True, message="Document uploaded successfully.", data=metadata)
#     except SensoryPlatformException as e:
#         return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
#     except Exception as e:
#         logger.error(f"Upload error: {str(e)}", exc_info=True)
#         return JSONResponse(status_code=500, content={"success": False, "message": "Internal server error."})

# # -----------------------------------------------------------------------------
# # 2. MASTER PROCESS PIPELINE (Background)
# # -----------------------------------------------------------------------------
# @router.post("/{document_id}/process", status_code=202)
# async def process_document(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(..., description="Document UUID")
# ):
#     metadata_path = settings.STORAGE_RAW_DIR / document_id / "metadata.json"
#     if not metadata_path.exists():
#         raise DocumentNotFoundError(document_id)

#     orchestrator = PipelineOrchestrator(document_id)
#     background_tasks.add_task(orchestrator.run_full_pipeline)

#     return {
#         "success": True,
#         "message": "Document processing started in the background.",
#         "data": {
#             "document_id": document_id,
#             "status": "RUNNING",
#             "status_endpoint": f"{settings.API_V1_STR}/documents/{document_id}/status"
#         }
#     }

# # -----------------------------------------------------------------------------
# # 3. PIPELINE STATUS
# # -----------------------------------------------------------------------------
# @router.get("/{document_id}/status", status_code=200)
# async def get_document_status(document_id: str = FastAPIPath(...)):
#     metadata_path = settings.STORAGE_RAW_DIR / document_id / "metadata.json"
#     if not metadata_path.exists():
#         raise DocumentNotFoundError(document_id)

#     with open(metadata_path, "r", encoding="utf-8") as f:
#         meta = json.load(f)

#     return {
#         "success": True,
#         "data": {
#             "document_id": document_id,
#             "status": meta.get("pipeline_status", "UNKNOWN"),
#             "progress": meta.get("progress", 0),
#             "current_stage": meta.get("current_stage", "PENDING"),
#             "completed_stages": meta.get("completed_stages", []),
#             "remaining_stages": meta.get("remaining_stages", [])
#         }
#     }

# # -----------------------------------------------------------------------------
# # 4. STRUCTURE EXTRACTION
# # -----------------------------------------------------------------------------
# @router.post("/{document_id}/extract-structure", status_code=200)
# async def extract_structure(
#     document_id: str = FastAPIPath(..., description="The unique document identifier"),
#     service: StructureService = Depends(get_structure_service)
# ):
#     """Extracts logical structure, layout semantics, tables, and images."""
#     logger.info(f"Triggering structural extraction for document ID: {document_id}")
#     try:
#         result = await service.build_structural_tree(document_id)
#         return {"success": True, "message": "Document structure extracted successfully.", "data": result}
#     except SensoryPlatformException as e:
#         return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

# @router.get("/{document_id}/structure", status_code=200)
# async def get_document_structure(document_id: str = FastAPIPath(...)):
#     """Retrieves the highly relational document_tree.json artifact."""
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
#     if not tree_path.exists():
#         raise DocumentNotFoundError(document_id)

#     with open(tree_path, "r", encoding="utf-8") as f:
#         data = json.load(f)
#     return {"success": True, "data": data}

# # -----------------------------------------------------------------------------
# # 5. KNOWLEDGE EXTRACTION
# # -----------------------------------------------------------------------------
# @router.post("/{document_id}/extract-knowledge", status_code=202)
# async def extract_knowledge(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(..., description="Unique document identifier"),
#     service: KnowledgeService = Depends(get_knowledge_service)
# ):
#     """Triggers contextual LLM extraction to build deduplicated nodes and relationships."""
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
#     if not tree_path.exists():
#         return JSONResponse(status_code=400, content={"success": False, "message": "Structure tree missing. Run /extract-structure first."})

#     background_tasks.add_task(service.extract_knowledge, document_id)
#     return {
#         "success": True,
#         "message": "Section-aware LLM extraction started in the background.",
#         "data": {
#             "document_id": document_id,
#             "pipeline_status": "EXTRACTING_KNOWLEDGE"
#         }
#     }

# @router.get("/{document_id}/knowledge", status_code=200)
# async def get_extracted_knowledge(document_id: str = FastAPIPath(...)):
#     """Returns the deduplicated, context-injected knowledge graph artifact."""
#     knowledge_path = settings.STORAGE_PROCESSED_DIR / document_id / "extracted_knowledge.json"
#     if not knowledge_path.exists():
#         return JSONResponse(status_code=202, content={"success": True, "message": "Knowledge extraction is still processing.", "data": None})

#     with open(knowledge_path, "r", encoding="utf-8") as f:
#         data = json.load(f)
        
#     return {
#         "success": True,
#         "data": {
#             "document_id": document_id,
#             "concepts": data.get("concepts", []),
#             "relationships": data.get("relationships", []),
#             "scientific_rules": data.get("scientific_rules", []),
#             "procedures": data.get("procedures", [])
#         }
#     }

# # -----------------------------------------------------------------------------
# # 6. CANONICAL MAPPING & PREVIEW
# # -----------------------------------------------------------------------------
# # @router.get("/{document_id}/canonical", status_code=200)
# # async def get_canonical(document_id: str = FastAPIPath(...)):
# #     mapping_path = settings.STORAGE_PROCESSED_DIR / document_id / "canonical_mapping.json"
# #     if not mapping_path.exists():
# #         return JSONResponse(status_code=400, content={"success": False, "message": "Canonical mapping pending."})

# #     with open(mapping_path, "r", encoding="utf-8") as f:
# #         data = json.load(f)
# #     return {"success": True, "data": data}

# # @router.get("/{document_id}/preview", status_code=200)
# # async def get_preview(document_id: str = FastAPIPath(...)):
# #     schema_path = settings.STORAGE_PROCESSED_DIR / document_id / "mysql_payload.json"
# #     if not schema_path.exists():
# #         return JSONResponse(status_code=400, content={"success": False, "message": "Schema mapping pending."})

# #     with open(schema_path, "r", encoding="utf-8") as f:
# #         payload = json.load(f)

# #     stats = payload.get("validation_stats", {})
# #     return {
# #         "success": True,
# #         "data": {
# #             "summary": {
# #                 "concepts": stats.get("proposals_generated", 0),
# #                 "relationships": stats.get("live_edges_ready", 0),
# #                 "new_proposals": stats.get("proposals_generated", 0)
# #             },
# #             "validation": "PASSED"
# #         }
# #     }


# from app.services.proposal_service import ProposalService

# def get_proposal_service() -> ProposalService:
#     return ProposalService()

# # 6. Trigger Canonical Mapping
# @router.post("/{document_id}/extract-canonical", status_code=200)
# async def extract_canonical(
#     document_id: str = FastAPIPath(...),
#     service: ProposalService = Depends(get_proposal_service)
# ):
#     """Maps extracted concepts against live Concept DB & Qdrant vectors to produce proposals."""
#     try:
#         result = await service.generate_canonical_mapping(document_id)
#         return {"success": True, "message": "Canonical mapping generated.", "data": result}
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

# # 7. Canonical Mapping Retrieval API
# @router.get("/{document_id}/canonical", status_code=200)
# async def get_canonical(document_id: str = FastAPIPath(...)):
#     mapping_path = settings.STORAGE_PROCESSED_DIR / document_id / "canonical_mapping.json"
#     if not mapping_path.exists():
#         return JSONResponse(status_code=400, content={"success": False, "message": "Canonical mapping pending."})

#     with open(mapping_path, "r", encoding="utf-8") as f:
#         data = json.load(f)
#     return {"success": True, "data": data}

# # 8. Preview API (Before MySQL Commit)
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
#             "validation": "PASSED",
#             "mysql_payload": payload
#         }
#     }


# # -----------------------------------------------------------------------------
# # 7. COMMIT
# # -----------------------------------------------------------------------------
# @router.post("/{document_id}/commit", status_code=200)
# async def commit_document(
#     document_id: str = FastAPIPath(...),
#     mysql_service: MySQLService = Depends(get_mysql_service)
# ):
#     try:
#         result = await mysql_service.commit_schema_to_db(document_id)
#         return {
#             "success": True,
#             "message": "Committed to MySQL successfully.",
#             "data": result
#         }
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"success": False, "message": str(e)})









# import json
# from pathlib import Path
# from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, Path as FastAPIPath, HTTPException
# from fastapi.responses import JSONResponse, FileResponse

# from app.services.document_service import DocumentService
# from app.services.pipeline_orchestrator import PipelineOrchestrator
# from app.services.proposal_service import ProposalService
# from app.services.mysql_service import MySQLService
# from app.services.structure_service import StructureService
# from app.services.knowledge_service import KnowledgeService
# from app.models.responses import UploadResponse
# from app.core.exceptions import SensoryPlatformException, DocumentNotFoundError, ProcessingError, StorageError
# from app.core.logger import logger
# from app.core.config import settings

# router = APIRouter(prefix="/documents", tags=["Enterprise Document Pipeline"])

# # Dependency Injections
# def get_document_service() -> DocumentService: return DocumentService()
# def get_proposal_service() -> ProposalService: return ProposalService()
# def get_mysql_service() -> MySQLService: return MySQLService()
# def get_structure_service() -> StructureService: return StructureService()
# def get_knowledge_service() -> KnowledgeService: return KnowledgeService()

# ###############################################################################
# # 1. INGESTION
# ###############################################################################

# @router.post("/upload", response_model=UploadResponse, status_code=201)
# async def upload_document(
#     file: UploadFile = File(..., description="Upload PDF, Book, or Research Paper"),
#     service: DocumentService = Depends(get_document_service)
# ):
#     logger.info(f"Incoming upload: {file.filename}")
#     try:
#         metadata = await service.process_upload(file)
#         return UploadResponse(success=True, message="Document uploaded successfully.", data=metadata)
#     except SensoryPlatformException as e:
#         raise HTTPException(status_code=e.status_code, detail=e.message)
#     except Exception as e:
#         logger.error(f"Upload error: {str(e)}", exc_info=True)
#         raise HTTPException(status_code=500, detail="Internal server error during upload.")

# ###############################################################################
# # 2. STATUS & TRACKING (Enterprise Job API)
# ###############################################################################

# @router.get("/{document_id}/status", status_code=200)
# async def get_document_status(document_id: str = FastAPIPath(...)):
#     """Returns granular, stage-by-stage pipeline status."""
#     metadata_path = settings.STORAGE_RAW_DIR / document_id / "metadata.json"
#     if not metadata_path.exists():
#         raise HTTPException(status_code=404, detail=f"Document {document_id} not found.")

#     with open(metadata_path, "r", encoding="utf-8") as f:
#         meta = json.load(f)

#     # Enterprise Status Shape
#     return {
#         "success": True,
#         "data": {
#             "document_id": document_id,
#             "global_status": meta.get("pipeline_status", "UNKNOWN"),
#             "progress_percent": meta.get("progress", 0),
#             "stages": {
#                 "structure_parsing": meta.get("stage_structure", "pending"),
#                 "knowledge_extraction": meta.get("stage_knowledge", "pending"),
#                 "canonical_mapping": meta.get("stage_canonical", "pending"),
#                 "validation": meta.get("stage_validation", "pending"),
#                 "mysql_commit": meta.get("stage_mysql", "pending"),
#                 "qdrant_sync": meta.get("stage_qdrant", "pending")
#             },
#             "audit_trail": {
#                 "created_at": meta.get("created_at"),
#                 "last_updated": meta.get("last_updated"),
#                 "processed_by_model": meta.get("model_version", "gpt-4o-mini")
#             }
#         }
#     }

# ###############################################################################
# # 3. ASYNC PIPELINE STAGES (202 Accepted Pattern)
# ###############################################################################

# @router.post("/{document_id}/process", status_code=202)
# async def process_document_full(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(...)
# ):
#     """Triggers the full end-to-end pipeline in the background."""
#     orchestrator = PipelineOrchestrator(document_id)
#     background_tasks.add_task(orchestrator.run_full_pipeline)
#     return JSONResponse(status_code=202, content={
#         "success": True, 
#         "message": "Full pipeline execution queued.",
#         "job_status_url": f"{settings.API_V1_STR}/documents/{document_id}/status"
#     })

# @router.post("/{document_id}/extract-structure", status_code=202)
# async def extract_structure_async(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(...),
#     service: StructureService = Depends(get_structure_service)
# ):
#     """Async Job: Extracts logical structure, layout semantics, tables, and images."""
#     background_tasks.add_task(service.build_structural_tree, document_id)
#     return JSONResponse(status_code=202, content={
#         "success": True, "message": "Structure extraction queued.",
#         "job_status_url": f"{settings.API_V1_STR}/documents/{document_id}/status"
#     })

# @router.post("/{document_id}/extract-knowledge", status_code=202)
# async def extract_knowledge_async(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(...),
#     service: KnowledgeService = Depends(get_knowledge_service)
# ):
#     """Async Job: Triggers contextual LLM extraction to build deduplicated nodes."""
#     background_tasks.add_task(service.extract_knowledge, document_id)
#     return JSONResponse(status_code=202, content={
#         "success": True, "message": "Knowledge extraction queued.",
#         "job_status_url": f"{settings.API_V1_STR}/documents/{document_id}/status"
#     })

# @router.post("/{document_id}/extract-canonical", status_code=202)
# async def extract_canonical_async(
#     background_tasks: BackgroundTasks,
#     document_id: str = FastAPIPath(...),
#     service: ProposalService = Depends(get_proposal_service)
# ):
#     """Async Job: Maps extracted concepts against live Concept DB & Qdrant vectors."""
#     background_tasks.add_task(service.generate_canonical_mapping, document_id)
#     return JSONResponse(status_code=202, content={
#         "success": True, "message": "Canonical mapping and proposal generation queued.",
#         "job_status_url": f"{settings.API_V1_STR}/documents/{document_id}/status"
#     })

# ###############################################################################
# # 4. ARTIFACT RETRIEVAL
# ###############################################################################

# @router.get("/{document_id}/structure", status_code=200)
# async def get_document_structure(document_id: str = FastAPIPath(...)):
#     tree_path = settings.STORAGE_PROCESSED_DIR / document_id / "document_tree.json"
#     if not tree_path.exists(): raise HTTPException(status_code=404, detail="Structure artifact not found.")
#     with open(tree_path, "r", encoding="utf-8") as f: return {"success": True, "data": json.load(f)}

# @router.get("/{document_id}/knowledge", status_code=200)
# async def get_extracted_knowledge(document_id: str = FastAPIPath(...)):
#     knowledge_path = settings.STORAGE_PROCESSED_DIR / document_id / "extracted_knowledge.json"
#     if not knowledge_path.exists(): raise HTTPException(status_code=404, detail="Knowledge artifact not found.")
#     with open(knowledge_path, "r", encoding="utf-8") as f: return {"success": True, "data": json.load(f)}

# @router.get("/{document_id}/canonical", status_code=200)
# async def get_canonical(document_id: str = FastAPIPath(...)):
#     mapping_path = settings.STORAGE_PROCESSED_DIR / document_id / "canonical_mapping.json"
#     if not mapping_path.exists(): raise HTTPException(status_code=404, detail="Canonical mapping artifact not found.")
#     with open(mapping_path, "r", encoding="utf-8") as f: return {"success": True, "data": json.load(f)}

# ###############################################################################
# # 5. PREVIEW & VALIDATION (ETL Checkpoints)
# ###############################################################################

# # @router.get("/{document_id}/preview", status_code=200)
# # async def get_preview_summary(document_id: str = FastAPIPath(...)):
# #     """Returns a lightweight summary of the MySQL payload (does not expose full JSON)."""
# #     schema_path = settings.STORAGE_PROCESSED_DIR / document_id / "mysql_payload.json"
# #     if not schema_path.exists():
# #         raise HTTPException(status_code=404, detail="MySQL payload pending.")

# #     with open(schema_path, "r", encoding="utf-8") as f:
# #         payload = json.load(f)

# #     # Return summary metrics only to prevent massive JSON payloads crashing the browser
# #     return {
# #         "success": True,
# #         "data": {
# #             "document_id": document_id,
# #             "proposals_requiring_review": len([p for p in payload.get("concept_proposals", []) if p.get("requires_expert")]),
# #             "auto_approved_proposals": len([p for p in payload.get("concept_proposals", []) if not p.get("requires_expert")]),
# #             "relationships_ready": len(payload.get("concept_relationships", [])),
# #             "download_url": f"{settings.API_V1_STR}/documents/{document_id}/preview/download"
# #         }
# #     }


# @router.get("/{document_id}/preview", status_code=200)
# async def get_preview_summary(document_id: str = FastAPIPath(...)):
#     """Returns a lightweight summary of the MySQL payload (does not expose full JSON)."""
#     schema_path = settings.STORAGE_PROCESSED_DIR / document_id / "mysql_payload.json"
#     if not schema_path.exists():
#         raise HTTPException(status_code=404, detail="MySQL payload pending.")

#     with open(schema_path, "r", encoding="utf-8") as f:
#         payload = json.load(f)

#     stats = payload.get("validation_stats", {})

#     # Correcting the false "Auto Approved" logic. 
#     # Mapped DB concepts are Reused. The rest are Pending Proposals (some require expert review).
#     return {
#         "success": True,
#         "data": {
#             "document_id": document_id,
#             "pipeline_state": "AWAITING_VALIDATION_OR_COMMIT",
#             "summary_metrics": {
#                 "existing_concepts_reused": stats.get("reused_concepts", 0),
#                 "proposals_requiring_expert_review": stats.get("proposals_requiring_review", 0),
#                 "proposals_standard_pending": stats.get("proposals_standard", 0),
#                 "relationships_mapped": stats.get("live_edges_ready", 0)
#             },
#             "download_url": f"{settings.API_V1_STR}/documents/{document_id}/preview/download"
#         }
#     }


# @router.get("/{document_id}/preview/download", status_code=200)
# async def download_preview_payload(document_id: str = FastAPIPath(...)):
#     """Allows downloading the raw, massive MySQL JSON payload for inspection."""
#     schema_path = settings.STORAGE_PROCESSED_DIR / document_id / "mysql_payload.json"
#     if not schema_path.exists():
#         raise HTTPException(status_code=404, detail="MySQL payload pending.")
#     return FileResponse(path=schema_path, media_type="application/json", filename=f"{document_id}_mysql_payload.json")

# @router.post("/{document_id}/validate", status_code=200)
# async def validate_payload(
#     document_id: str = FastAPIPath(...),
#     mysql_service: MySQLService = Depends(get_mysql_service)
# ):
#     """Pre-flight check: Validates ontology, prevents duplicates, checks orphans before commit."""
#     try:
#         validation_report = await mysql_service.validate_schema_payload(document_id)
#         if not validation_report.get("is_valid"):
#             raise HTTPException(status_code=422, detail={"message": "Validation Failed", "errors": validation_report["errors"]})
#         return {"success": True, "message": "Payload is valid and ready for commit.", "data": validation_report}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# ###############################################################################
# # 6. EXPERT APPROVAL WORKFLOW (Concept DB Governance)
# ###############################################################################

# @router.post("/proposals/{proposal_uid}/approve", status_code=200)
# async def approve_proposal(
#     proposal_uid: str, 
#     service: ProposalService = Depends(get_proposal_service)
# ):
#     """Approves a pending proposal and promotes it to a live concept."""
#     try:
#         result = await service.approve_proposal(proposal_uid)
#         return {"success": True, "message": f"Proposal {proposal_uid} approved.", "data": result}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/proposals/{proposal_uid}/reject", status_code=200)
# async def reject_proposal(
#     proposal_uid: str, 
#     service: ProposalService = Depends(get_proposal_service)
# ):
#     """Rejects a pending proposal."""
#     try:
#         await service.reject_proposal(proposal_uid)
#         return {"success": True, "message": f"Proposal {proposal_uid} rejected."}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# # @router.post("/proposals/bulk-approve", status_code=200)
# # async def bulk_approve_proposals(
# #     proposal_uids: list[str], 
# #     service: ProposalService = Depends(get_proposal_service)
# # ):
# #     """Approves multiple proposals simultaneously."""
# #     try:
# #         result = await service.bulk_approve_proposals(proposal_uids)
# #         return {"success": True, "message": "Bulk approval successful.", "data": result}
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=str(e))

# ###############################################################################
# # 7. COMMIT & ROLLBACK
# ###############################################################################

# # @router.post("/{document_id}/commit", status_code=200)
# # async def commit_document(
# #     document_id: str = FastAPIPath(...),
# #     mysql_service: MySQLService = Depends(get_mysql_service)
# # ):
# #     """
# #     Final ETL Step: Writes proposals, relationships, and terms to MySQL, 
# #     triggers Qdrant sync, and logs the audit trail.
# #     """
# #     try:
# #         result = await mysql_service.commit_schema_to_db(document_id)
# #         return {"success": True, "message": "Committed to Concept DB successfully.", "data": result}
# #     except Exception as e:
# #         logger.error(f"Commit failed for {document_id}: {str(e)}", exc_info=True)
# #         raise HTTPException(status_code=500, detail="Commit transaction failed. Check logs.")

# # @router.post("/{document_id}/rollback", status_code=200)
# # async def rollback_document(
# #     document_id: str = FastAPIPath(...),
# #     mysql_service: MySQLService = Depends(get_mysql_service)
# # ):
# #     """Emergency Revert: Rolls back partial DB inserts and Qdrant vectors if pipeline crashed."""
# #     try:
# #         await mysql_service.rollback_document_transaction(document_id)
# #         return {"success": True, "message": f"Rolled back transactions for {document_id}."}
# #     except Exception as e:
# #         logger.error(f"Rollback failed for {document_id}: {str(e)}", exc_info=True)
# #         raise HTTPException(status_code=500, detail="Rollback failed. Manual database intervention may be required.")



# import json
# from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, Path as FastAPIPath, HTTPException
# from fastapi.responses import JSONResponse

# from app.services.document_service import DocumentService
# from app.services.pipeline_orchestrator import PipelineOrchestrator
# from app.services.proposal_service import ProposalService
# from app.services.mysql_service import MySQLService
# from app.core.logger import logger
# from app.core.config import settings

# router = APIRouter(prefix="/documents", tags=["Enterprise Document Pipeline"])

# def get_proposal_service() -> ProposalService: return ProposalService()
# def get_mysql_service() -> MySQLService: return MySQLService()

# ###############################################################################
# # VALIDATION DASHBOARD (Replaces "Preview")
# ###############################################################################

# @router.get("/{document_id}/dashboard/validation", status_code=200)
# async def get_validation_dashboard(
#     document_id: str = FastAPIPath(...),
#     page: int = 1,
#     limit: int = 50,
#     mysql_service: MySQLService = Depends(get_mysql_service)
# ):
#     """
#     Returns a paginated view of staging proposals for the Expert Review Dashboard.
#     Does NOT dump the entire JSON payload to the client.
#     """
#     try:
#         # Fetches paginated staging data from the database
#         dashboard_data = await mysql_service.get_staging_dashboard(document_id, page, limit)
#         if not dashboard_data:
#             raise HTTPException(status_code=404, detail="No staging data found. Pipeline may still be running.")
            
#         return {
#             "success": True,
#             "data": dashboard_data
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# ###############################################################################
# # EXPERT APPROVAL WORKFLOW
# ###############################################################################

# @router.post("/proposals/{staging_ref}/approve", status_code=200)
# async def approve_merge_or_proposal(
#     staging_ref: str, 
#     action: str = "approve_as_new",  # Can be "approve_as_new" or "approve_merge"
#     mysql_service: MySQLService = Depends(get_mysql_service)
# ):
#     """Expert-in-the-loop: Flags a staging proposal as approved."""
#     try:
#         await mysql_service.flag_staging_proposal(staging_ref, status="approved", action=action)
#         return {"success": True, "message": f"Proposal {staging_ref} marked approved."}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/proposals/bulk-approve", status_code=200)
# async def bulk_approve_proposals(
#     staging_refs: list[str], 
#     mysql_service: MySQLService = Depends(get_mysql_service)
# ):
#     """Approves a batch of staging proposals."""
#     try:
#         await mysql_service.bulk_flag_staging_proposals(staging_refs, status="approved")
#         return {"success": True, "message": f"{len(staging_refs)} proposals marked approved."}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# ###############################################################################
# # TRANSACTION CONTROL (COMMIT & ROLLBACK)
# ###############################################################################

# @router.post("/{document_id}/commit", status_code=200)
# async def commit_document(
#     document_id: str = FastAPIPath(...),
#     mysql_service: MySQLService = Depends(get_mysql_service)
# ):
#     """
#     Final ETL Step: 
#     1. BEGIN TRANSACTION.
#     2. Writes approved proposals to `concepts` / `concept_proposals`.
#     3. Replaces `staging_ref` with real DB auto-increment UIDs.
#     4. Inserts `concept_relationships`.
#     5. COMMIT TRANSACTION.
#     6. Triggers Qdrant sync.
#     """
#     try:
#         result = await mysql_service.commit_staging_to_live_db(document_id)
#         return {"success": True, "message": "Committed to Concept DB successfully.", "data": result}
#     except Exception as e:
#         logger.error(f"Commit failed for {document_id}: {str(e)}", exc_info=True)
#         # The mysql_service handles the SQL ROLLBACK internally upon failure
#         raise HTTPException(status_code=500, detail="Commit transaction failed and was rolled back. Check logs.")

# @router.post("/{document_id}/rollback", status_code=200)
# async def clear_staging_data(
#     document_id: str = FastAPIPath(...),
#     mysql_service: MySQLService = Depends(get_mysql_service)
# ):
#     """Drops the staging payload from the database if the extraction is rejected."""
#     try:
#         await mysql_service.drop_staging_payload(document_id)
#         return {"success": True, "message": f"Staging data cleared for {document_id}."}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))