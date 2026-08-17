class SensoryPlatformException(Exception):
    """Base exception for all platform errors."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class DocumentNotFoundError(SensoryPlatformException):
    """Raised when a requested document ID does not exist in the repository."""
    def __init__(self, document_id: str):
        super().__init__(f"Document with ID {document_id} was not found.", status_code=404)

class InvalidFileTypeError(SensoryPlatformException):
    """Raised when the uploaded file is not a supported type."""
    def __init__(self, filename: str):
        super().__init__(f"File '{filename}' has an unsupported extension. Only PDFs are allowed.", status_code=400)

class FileTooLargeError(SensoryPlatformException):
    """Raised when the uploaded file exceeds the configured size limit."""
    def __init__(self, size_mb: float, limit_mb: float):
        super().__init__(f"File size ({size_mb:.2f} MB) exceeds the maximum limit of {limit_mb} MB.", status_code=413)

class StorageError(SensoryPlatformException):
    """Raised when file I/O operations fail in the storage manager."""
    def __init__(self, detail: str):
        super().__init__(f"Storage operation failed: {detail}", status_code=500)

class ProcessingError(SensoryPlatformException):
    def __init__(self, message: str = "Document processing failed."):
        super().__init__(status_code=500, message=message)