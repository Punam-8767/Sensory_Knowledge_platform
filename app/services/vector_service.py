import json
from pathlib import Path
from typing import Dict, Any, List
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings
from app.core.logger import logger
from app.core.exceptions import ProcessingError

class VectorService:
    def __init__(self):
        self.processed_dir = settings.STORAGE_PROCESSED_DIR
        # Initialize persistent ChromaDB client matching your stack
        self.chroma_client = chromadb.PersistentClient(
            path=str(settings.VECTOR_DB_DIR if hasattr(settings, "VECTOR_DB_DIR") else self.processed_dir / "chroma_db")
        )
        self.collection_name = "document_embeddings"

    async def index_document_structure(self, document_id: str) -> Dict[str, Any]:
        """Reads the structural document_tree.json, chunks text segments logically,
        embeds them, and indexes them into ChromaDB.
        """
        doc_output_dir = self.processed_dir / document_id
        tree_path = doc_output_dir / "document_tree.json"
        
        if not tree_path.exists():
            raise ProcessingError(f"Document tree not found for {document_id}. Run structural extraction first.")

        try:
            with open(tree_path, "r", encoding="utf-8") as f:
                doc_tree = json.load(f)

            collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )

            chunks_to_add = []
            metadatas_to_add = []
            ids_to_add = []

            chunk_counter = 0
            for page in doc_tree.get("pages", []):
                page_num = page.get("page_number")
                current_headings = page.get("headings", [])
                active_heading = current_headings[0] if current_headings else "General"

                for elem in page.get("elements", []):
                    if elem.get("type") in ["paragraph", "heading"]:
                        text = elem.get("text", "").strip()
                        if not text:
                            continue
                        
                        # Create unique identifiers and rich contextual metadata
                        chunk_id = f"{document_id}_p{page_num}_c{chunk_counter}"
                        metadata = {
                            "document_id": document_id,
                            "page_number": page_num,
                            "element_type": elem.get("type"),
                            "section_heading": active_heading,
                            "font_size": elem.get("font_size", 0.0),
                            "is_bold": str(elem.get("is_bold", False))
                        }

                        chunks_to_add.append(text)
                        metadatas_to_add.append(metadata)
                        ids_to_add.append(chunk_id)
                        chunk_counter += 1

                    elif elem.get("type") == "table":
                        # Convert tabular payload to markdown text representation for vectorization searchability
                        table_rows = elem.get("rows", [])
                        table_text = "\n".join([" | ".join([str(cell or "") for cell in row]) for row in table_rows])
                        if not table_text.strip():
                            continue

                        chunk_id = f"{document_id}_p{page_num}_table_{elem.get('table_index')}"
                        metadata = {
                            "document_id": document_id,
                            "page_number": page_num,
                            "element_type": "table",
                            "section_heading": active_heading,
                            "row_count": elem.get("row_count", 0),
                            "col_count": elem.get("col_count", 0)
                        }

                        chunks_to_add.append(f"Table Structure:\n{table_text}")
                        metadatas_to_add.append(metadata)
                        ids_to_add.append(chunk_id)

            # Batch upsert into ChromaDB collection if records exist
            if chunks_to_add:
                # Chroma's default embedding function handles text embedding automatically
                collection.upsert(
                    documents=chunks_to_add,
                    metadatas=metadatas_to_add,
                    ids=ids_to_add
                )

            logger.info(f"Successfully indexed {len(chunks_to_add)} chunks for document {document_id} into ChromaDB.")
            
            return {
                "document_id": document_id,
                "indexed_chunks_count": len(chunks_to_add),
                "vector_store": "ChromaDB",
                "collection": self.collection_name
            }

        except Exception as e:
            logger.error(f"Error vectorizing and indexing document {document_id}: {str(e)}", exc_info=True)
            raise ProcessingError(f"Failed to index document elements: {str(e)}")

        