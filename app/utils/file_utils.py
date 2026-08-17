import fitz  # PyMuPDF
from app.core.exceptions import SensoryPlatformException
from app.core.logger import logger

def validate_and_extract_pdf_metadata(file_path: str) -> dict:
    """
    Opens the PDF to verify it is a valid, readable file and extracts structural metadata.
    """
    try:
        # fitz.open is extremely fast; it only reads the cross-reference table initially
        with fitz.open(file_path) as doc:
            if doc.is_encrypted:
                raise SensoryPlatformException("Encrypted PDFs are not supported.", status_code=400)
            
            page_count = len(doc)
            if page_count == 0:
                raise SensoryPlatformException("The PDF file appears to be empty (0 pages).", status_code=400)
            
            return {
                "page_count": page_count
            }
            
    except fitz.FileDataError as e:
        logger.error(f"Corrupt or invalid PDF file detected at {file_path}: {str(e)}")
        raise SensoryPlatformException("The uploaded file is corrupt or is not a valid PDF.", status_code=400)
    except Exception as e:
        # If we already raised a SensoryPlatformException, just pass it up
        if isinstance(e, SensoryPlatformException):
            raise e
            
        logger.error(f"Unexpected error reading PDF {file_path}: {str(e)}")
        raise SensoryPlatformException("Failed to parse the PDF file.", status_code=500)