import json
import hashlib
import aiofiles
from pathlib import Path
from fastapi import UploadFile
from app.core.config import settings
from app.core.exceptions import StorageError
from app.core.logger import logger

class StorageManager:
    def __init__(self):
        self.raw_dir = settings.STORAGE_RAW_DIR
        self.processed_dir = settings.STORAGE_PROCESSED_DIR

    def _get_raw_workspace(self, document_id: str) -> Path:
        """Creates and returns the isolated raw workspace path for a document."""
        workspace = self.raw_dir / document_id
        workspace.mkdir(parents=True, exist_ok=True)
        # Also pre-create the processed workspace for later stages
        (self.processed_dir / document_id).mkdir(parents=True, exist_ok=True)
        return workspace

    async def save_raw_file(self, document_id: str, file: UploadFile) -> dict:
        """Saves the uploaded file in chunks and calculates SHA-256 checksum concurrently."""
        workspace = self._get_raw_workspace(document_id)
        file_path = workspace / "original.pdf"
        
        sha256_hash = hashlib.sha256()
        file_size = 0
        
        try:
            # Stream in 1MB chunks to keep memory usage low
            async with aiofiles.open(file_path, 'wb') as out_file:
                while content := await file.read(1024 * 1024):  
                    await out_file.write(content)
                    sha256_hash.update(content)
                    file_size += len(content)
                    
            logger.info(f"Saved {file.filename} to {file_path}")
            
            return {
                "file_path": str(file_path.relative_to(settings.BASE_DIR)),
                "size_bytes": file_size,
                "checksum": sha256_hash.hexdigest()
            }
        except Exception as e:
            logger.error(f"Failed to save file {file.filename}: {str(e)}")
            raise StorageError(f"File write operation failed: {str(e)}")
        finally:
            await file.seek(0)  # Reset pointer just in case

    def save_metadata(self, document_id: str, metadata: dict) -> str:
        """Saves the document state and metadata as a JSON file."""
        workspace = self._get_raw_workspace(document_id)
        metadata_path = workspace / "metadata.json"
        
        try:
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            return str(metadata_path.relative_to(settings.BASE_DIR))
        except Exception as e:
            logger.error(f"Failed to write metadata for {document_id}: {str(e)}")
            raise StorageError(f"Failed to write metadata.json: {str(e)}")