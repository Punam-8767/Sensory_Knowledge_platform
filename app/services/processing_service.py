import json
import fitz  # PyMuPDF
from pathlib import Path
from app.core.config import settings
from app.core.exceptions import DocumentNotFoundError, StorageError
from app.core.logger import logger

class ProcessingService:
    def __init__(self):
        self.raw_dir = settings.STORAGE_RAW_DIR
        self.processed_dir = settings.STORAGE_PROCESSED_DIR

    def _setup_processed_workspace(self, document_id: str) -> dict:
        """Creates subdirectories for processing artifacts under storage/processed/{document_id}/."""
        base_path = self.processed_dir / document_id
        pages_path = base_path / "pages"
        images_path = base_path / "images"
        tables_path = base_path / "tables"
        charts_path = base_path / "charts"

        for directory in [pages_path, images_path, tables_path, charts_path]:
            directory.mkdir(parents=True, exist_ok=True)

        return {
            "base": base_path,
            "pages": pages_path,
            "images": images_path,
            "tables": tables_path,
            "charts": charts_path
        }

    async def process_document(self, document_id: str) -> dict:
        """Extracts text pages, images, and builds the initial document tree."""
        raw_pdf_path = self.raw_dir / document_id / "original.pdf"
        metadata_path = self.raw_dir / document_id / "metadata.json"

        if not raw_pdf_path.exists():
            raise DocumentNotFoundError(document_id)

        paths = self._setup_processed_workspace(document_id)
        
        extracted_pages = []
        total_images_extracted = 0

        try:
            logger.info(f"Starting pipeline extraction for {document_id}")
            with fitz.open(raw_pdf_path) as doc:
                for page_idx, page in enumerate(doc, start=1):
                    # 1. Extract text and page layout
                    text = page.get_text("text")
                    page_filename = f"page_{page_idx}.txt"
                    with open(paths["pages"] / page_filename, "w", encoding="utf-8") as f:
                        f.write(text)

                    # 2. Extract embedded images
                    image_list = page.get_images(full=True)
                    page_images = []
                    for img_idx, img_info in enumerate(image_list, start=1):
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        
                        image_filename = f"page_{page_idx}_img_{img_idx}.{image_ext}"
                        img_save_path = paths["images"] / image_filename
                        with open(img_save_path, "wb") as f_img:
                            f_img.write(image_bytes)

                        page_images.append(str(img_save_path.relative_to(settings.BASE_DIR)))
                        total_images_extracted += 1

                    extracted_pages.append({
                        "page_number": page_idx,
                        "character_count": len(text),
                        "word_count": len(text.split()),
                        "images_count": len(page_images),
                        "images": page_images,
                        "content_preview": text[:200].strip() if text else ""
                    })

            # 3. Generate document_tree.json
            document_tree = {
                "document_id": document_id,
                "total_pages": len(extracted_pages),
                "total_images_extracted": total_images_extracted,
                "artifacts": {
                    "pages_dir": str(paths["pages"].relative_to(settings.BASE_DIR)),
                    "images_dir": str(paths["images"].relative_to(settings.BASE_DIR)),
                    "tables_dir": str(paths["tables"].relative_to(settings.BASE_DIR)),
                    "charts_dir": str(paths["charts"].relative_to(settings.BASE_DIR))
                },
                "pages": extracted_pages
            }

            tree_file_path = paths["base"] / "document_tree.json"
            with open(tree_file_path, "w", encoding="utf-8") as f:
                json.dump(document_tree, f, indent=2)

            # 4. Update status in metadata.json
            if metadata_path.exists():
                with open(metadata_path, "r+", encoding="utf-8") as f:
                    meta_data = json.load(f)
                    meta_data["pipeline_status"] = "PROCESSED"
                    meta_data["next_step"] = f"{settings.API_V1_STR}/documents/{document_id}/tree"
                    f.seek(0)
                    json.dump(meta_data, f, indent=2)
                    f.truncate()

            logger.info(f"Successfully processed {document_id}")
            return {
                "document_id": document_id,
                "pipeline_status": "PROCESSED",
                "processed_pages": len(extracted_pages),
                "extracted_images": total_images_extracted,
                "document_tree_path": str(tree_file_path.relative_to(settings.BASE_DIR)),
                "next_step": f"{settings.API_V1_STR}/documents/{document_id}/tree"
            }

        except Exception as e:
            logger.error(f"Error processing document {document_id}: {str(e)}")
            raise StorageError(f"Processing failed: {str(e)}")

        