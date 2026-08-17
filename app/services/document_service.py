import uuid
import os
from fastapi import UploadFile
from app.core.config import settings
from app.core.exceptions import InvalidFileTypeError, FileTooLargeError
from app.storage.storage_manager import StorageManager
from app.utils.file_utils import validate_and_extract_pdf_metadata
from app.models.responses import DocumentMetadata, StoragePaths

class DocumentService:
    def __init__(self):
        self.storage_manager = StorageManager()

    def _generate_document_id(self) -> str:
        """Generates a short, collision-resistant UUID (e.g., doc_f3b81a62)."""
        return f"doc_{uuid.uuid4().hex[:8]}"

    def _validate_file_pre_upload(self, file: UploadFile):
        """Validates basic file attributes before starting the disk I/O."""
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise InvalidFileTypeError(file.filename)
            
        # FastAPI >0.100 exposes file.size
        if file.size and file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise FileTooLargeError(
                size_mb=file.size / (1024 * 1024), 
                limit_mb=settings.MAX_UPLOAD_SIZE_MB
            )

    async def process_upload(self, file: UploadFile) -> DocumentMetadata:
        """Executes the complete upload pipeline for a new document."""
        # 1. Pre-upload validation
        self._validate_file_pre_upload(file)
        
        # 2. Generate Workspace ID
        doc_id = self._generate_document_id()
        
        # 3. Save raw file to disk (calculates size & checksum)
        saved_file_info = await self.storage_manager.save_raw_file(doc_id, file)
        
        # 4. Check actual size post-upload (fallback if file.size was None)
        size_mb = saved_file_info["size_bytes"] / (1024 * 1024)
        if size_mb > settings.MAX_UPLOAD_SIZE_MB:
            raise FileTooLargeError(size_mb=size_mb, limit_mb=settings.MAX_UPLOAD_SIZE_MB)
            
        # 5. Extract PDF metadata (validates PDF integrity)
        pdf_metadata = validate_and_extract_pdf_metadata(
            file_path=os.path.join(settings.BASE_DIR, saved_file_info["file_path"])
        )
        
        # 6. Build the metadata object
        metadata_obj = DocumentMetadata(
            document_id=doc_id,
            filename=file.filename,
            document_type="book",
            mime_type=file.content_type or "application/pdf",
            file_size_mb=round(size_mb, 2),
            page_count=pdf_metadata["page_count"],
            checksum=saved_file_info["checksum"],
            storage=StoragePaths(
                raw_file=saved_file_info["file_path"],
                metadata_file="" # Will be populated in the next step
            ),
            pipeline_status="UPLOADED",
            next_step=f"{settings.API_V1_STR}/documents/{doc_id}/process"
        )
        
        # 7. Save metadata.json to disk
        metadata_path = self.storage_manager.save_metadata(doc_id, metadata_obj.model_dump())
        metadata_obj.storage.metadata_file = metadata_path
        
        return metadata_obj


    