from pydantic import BaseModel, Field
from typing import Optional

class StoragePaths(BaseModel):
    raw_file: str = Field(..., description="Path to the immutable original PDF.")
    metadata_file: str = Field(..., description="Path to the JSON metadata file.")

class DocumentMetadata(BaseModel):
    document_id: str = Field(..., description="Unique UUID for the document workspace.")
    filename: str = Field(..., description="Original uploaded filename.")
    document_type: str = Field(default="book", description="Classification of the document.")
    mime_type: str = Field(..., description="MIME type, usually application/pdf.")
    file_size_mb: float = Field(..., description="Size of the file in megabytes.")
    page_count: int = Field(..., description="Total number of pages in the PDF.")
    checksum: str = Field(..., description="SHA-256 checksum of the file for integrity verification.")
    storage: StoragePaths
    pipeline_status: str = Field(default="UPLOADED", description="Current stage in the processing pipeline.")
    next_step: str = Field(..., description="API endpoint to trigger the next pipeline stage.")

class UploadResponse(BaseModel):
    success: bool = Field(default=True)
    message: str = Field(default="Document uploaded successfully.")
    data: DocumentMetadata