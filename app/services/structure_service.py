# import json
# import re
# import fitz  # PyMuPDF
# from pathlib import Path
# from app.core.config import settings
# from app.core.exceptions import DocumentNotFoundError, StorageError
# from app.core.logger import logger

# class StructureService:
#     def __init__(self):
#         self.raw_dir = settings.STORAGE_RAW_DIR
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR

#     def _extract_toc(self, doc: fitz.Document) -> list[dict]:
#         """Extracts native Table of Contents if available in the PDF outline."""
#         toc = doc.get_toc()
#         structured_toc = []
#         for item in toc:
#             level, title, page = item
#             structured_toc.append({
#                 "level": level,
#                 "title": title.strip(),
#                 "page": page
#             })
#         return structured_toc

#     def _detect_headings_and_sections(self, page: fitz.Page, page_num: int) -> list[dict]:
#         """Analyzes text blocks and font metrics to identify structural headings."""
#         blocks = page.get_text("dict")["blocks"]
#         structural_elements = []

#         for b in blocks:
#             if b.get("type") == 0:  # Text block
#                 block_text = ""
#                 max_font_size = 0
#                 is_bold = False

#                 for line in b["lines"]:
#                     for span in line["spans"]:
#                         text = span["text"].strip()
#                         if text:
#                             block_text += text + " "
#                             if span["size"] > max_font_size:
#                                 max_font_size = span["size"]
#                             if "bold" in span["font"].lower() or "black" in span["font"].lower():
#                                 is_bold = True

#                 clean_text = block_text.strip()
#                 if not clean_text:
#                     continue

#                 # Classify potential structural elements based on font cues or patterns
#                 is_heading = max_font_size > 12 or (is_bold and len(clean_text) < 120)
#                 chapter_match = re.match(r"^(CHAPTER|Section|PART)\s+\d+", clean_text, re.IGNORECASE)

#                 element_type = "heading" if (is_heading or chapter_match) else "paragraph"

#                 structural_elements.append({
#                     "type": element_type,
#                     "text": clean_text,
#                     "font_size": round(max_font_size, 1),
#                     "is_bold": is_bold,
#                     "bbox": [round(x, 1) for x in b["bbox"]]
#                 })

#         return structural_elements

#     async def build_structural_tree(self, document_id: str) -> dict:
#         """Constructs a high-accuracy structural representation of the document."""
#         raw_pdf_path = self.raw_dir / document_id / "original.pdf"
#         processed_base = self.processed_dir / document_id
#         metadata_path = self.raw_dir / document_id / "metadata.json"

#         if not raw_pdf_path.exists():
#             raise DocumentNotFoundError(document_id)

#         try:
#             logger.info(f"Extracting document structure for {document_id}")
            
#             with fitz.open(raw_pdf_path) as doc:
#                 toc = self._extract_toc(doc)
#                 pages_structure = []

#                 for page_idx, page in enumerate(doc, start=1):
#                     elements = self._detect_headings_and_sections(page, page_idx)
                    
#                     # Extract page-level structural metadata
#                     headings = [e["text"] for e in elements if e["type"] == "heading"]
#                     full_page_text = "\n\n".join([e["text"] for e in elements])

#                     pages_structure.append({
#                         "page_number": page_idx,
#                         "headings": headings,
#                         "elements_count": len(elements),
#                         "elements": elements,
#                         "full_text": full_page_text
#                     })

#             structural_tree = {
#                 "document_id": document_id,
#                 "total_pages": len(pages_structure),
#                 "has_native_toc": len(toc) > 0,
#                 "table_of_contents": toc,
#                 "pages": pages_structure
#             }

#             # Save high-accuracy document tree
#             tree_file_path = processed_base / "document_tree.json"
#             processed_base.mkdir(parents=True, exist_ok=True)
            
#             with open(tree_file_path, "w", encoding="utf-8") as f:
#                 json.dump(structural_tree, f, indent=2)

#             # Update status in metadata.json
#             if metadata_path.exists():
#                 with open(metadata_path, "r+", encoding="utf-8") as f:
#                     meta_data = json.load(f)
#                     meta_data["pipeline_status"] = "STRUCTURE_EXTRACTED"
#                     meta_data["next_step"] = f"{settings.API_V1_STR}/documents/{document_id}/structure"
#                     f.seek(0)
#                     json.dump(meta_data, f, indent=2)
#                     f.truncate()

#             logger.info(f"Successfully generated structural tree for {document_id}")

#             return {
#                 "document_id": document_id,
#                 "pipeline_status": "STRUCTURE_EXTRACTED",
#                 "total_pages": len(pages_structure),
#                 "toc_entries_found": len(toc),
#                 "document_tree_path": str(tree_file_path.relative_to(settings.BASE_DIR)),
#                 "next_step": f"{settings.API_V1_STR}/documents/{document_id}/structure"
#             }

#         except Exception as e:
#             logger.error(f"Structure extraction failed for {document_id}: {str(e)}")
#             raise StorageError(f"Structure extraction failed: {str(e)}")







# import fitz  # PyMuPDF
# from pathlib import Path
# from typing import Dict, Any, List
# from app.core.config import settings
# from app.core.exceptions import DocumentNotFoundError, ProcessingError
# from app.core.logger import logger

# class StructureService:
#     def __init__(self):
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR

#     async def build_structural_tree(self, document_id: str) -> Dict[str, Any]:
#         """Extracts text elements, tables, and images with bounding boxes and page numbers."""
#         doc_dir = self.processed_dir / document_id
#         pdf_path = doc_dir / "document.pdf"

#         if not pdf_path.exists():
#             logger.error(f"PDF document not found for ID: {document_id} at {pdf_path}")
#             raise DocumentNotFoundError(document_id)

#         try:
#             doc = fitz.open(pdf_path)
#             total_pages = len(doc)
            
#             # 1. Extract Native Table of Contents
#             toc = doc.get_toc()
#             formatted_toc = [
#                 {"level": item[0], "title": item[1], "page_number": item[2]}
#                 for item in toc
#             ]

#             pages_data = []

#             for page_index, page in enumerate(doc):
#                 page_number = page_index + 1
#                 elements: List[Dict[str, Any]] = []
#                 headings: List[str] = []

#                 # --- A. Extract Tables ---
#                 try:
#                     tabs = page.find_tables()
#                     table_rects = []
#                     for tab in tabs:
#                         bbox = [round(v, 1) for v in list(tab.bbox)]
#                         table_rects.append(fitz.Rect(bbox))
                        
#                         # Extract table grid cells
#                         rows_data = tab.extract()
                        
#                         elements.append({
#                             "type": "table",
#                             "bbox": bbox,
#                             "row_count": tab.row_count,
#                             "col_count": tab.col_count,
#                             "rows": rows_data
#                         })
#                 except Exception as table_err:
#                     logger.warning(f"Table extraction failed on page {page_number}: {str(table_err)}")

#                 # --- B. Extract Images ---
#                 try:
#                     image_info_list = page.get_images(full=True)
#                     for img_index, img_info in enumerate(image_info_list):
#                         xref = img_info[0]
#                         rects = page.get_image_rects(xref)
#                         for rect in rects:
#                             bbox = [round(rect.x0, 1), round(rect.y0, 1), round(rect.x1, 1), round(rect.y1, 1)]
                            
#                             # Standard image artifact path relative to process storage
#                             img_relative_path = f"/storage/processed/{document_id}/images/page_{page_number}_img_{img_index + 1}.png"
                            
#                             elements.append({
#                                 "type": "image",
#                                 "xref": xref,
#                                 "image_index": img_index + 1,
#                                 "bbox": bbox,
#                                 "image_path": img_relative_path
#                             })
#                 except Exception as img_err:
#                     logger.warning(f"Image extraction failed on page {page_number}: {str(img_err)}")

#                 # --- C. Extract Text Blocks & Headings ---
#                 text_page = page.get_text("dict")
#                 page_text_blocks = []

#                 for block in text_page.get("blocks", []):
#                     # Check if block is a text block (type 0)
#                     if block.get("type") == 0:
#                         block_text = ""
#                         max_font_size = 0.0
#                         is_bold = False
                        
#                         for line in block.get("lines", []):
#                             for span in line.get("spans", []):
#                                 span_text = span.get("text", "").strip()
#                                 if span_text:
#                                     block_text += span_text + " "
#                                     font_size = round(span.get("size", 0.0), 1)
#                                     if font_size > max_font_size:
#                                         max_font_size = font_size
                                    
#                                     # Detect bold weight from font flags or name
#                                     flags = span.get("flags", 0)
#                                     font_name = span.get("font", "").lower()
#                                     if (flags & 2 != 0) or ("bold" in font_name):
#                                         is_bold = True

#                         clean_text = block_text.strip()
#                         if clean_text:
#                             page_text_blocks.append(clean_text)
#                             bbox = [round(v, 1) for v in block.get("bbox", [0, 0, 0, 0])]

#                             # Categorize Headings vs Paragraphs (Threshold: size >= 14pt or Bold >= 12pt)
#                             if max_font_size >= 14.0 or (is_bold and max_font_size >= 12.0):
#                                 elem_type = "heading"
#                                 headings.append(clean_text)
#                             else:
#                                 elem_type = "paragraph"

#                             elements.append({
#                                 "type": elem_type,
#                                 "text": clean_text,
#                                 "font_size": max_font_size,
#                                 "is_bold": is_bold,
#                                 "bbox": bbox
#                             })

#                 # Sort elements vertically by their y0 coordinate (bbox[1])
#                 elements.sort(key=lambda x: x.get("bbox", [0, 0, 0, 0])[1])

#                 full_page_text = "\n\n".join(page_text_blocks)

#                 pages_data.append({
#                     "page_number": page_number,
#                     "headings": headings,
#                     "elements_count": len(elements),
#                     "elements": elements,
#                     "full_text": full_page_text
#                 })

#             doc.close()

#             structural_tree = {
#                 "document_id": document_id,
#                 "total_pages": total_pages,
#                 "has_native_toc": len(formatted_toc) > 0,
#                 "table_of_contents": formatted_toc,
#                 "pages": pages_data
#             }

#             # Save the document_tree.json artifact
#             tree_path = doc_dir / "document_tree.json"
#             import json
#             with open(tree_path, "w", encoding="utf-8") as f:
#                 json.dump(structural_tree, f, indent=4, ensure_ascii=False)

#             return structural_tree

#         except Exception as e:
#             logger.error(f"Error processing structural tree for document {document_id}: {str(e)}", exc_info=True)
#             raise ProcessingError(f"Failed to build structural tree: {str(e)}")





# import fitz  # PyMuPDF
# import pdfplumber
# import json
# from pathlib import Path
# from typing import Dict, Any, List
# from app.core.config import settings
# from app.core.logger import logger
# from app.core.exceptions import DocumentNotFoundError, ProcessingError

# class StructureService:
#     def __init__(self):
#         self.raw_dir = Path(settings.STORAGE_RAW_DIR)
#         self.processed_dir = Path(settings.STORAGE_PROCESSED_DIR)

#     def _find_pdf_path(self, document_id: str) -> Path:
#         """Finds the PDF file across raw and processed directories."""
#         candidate_paths = [
#             self.raw_dir / f"{document_id}.pdf",
#             self.processed_dir / document_id / f"{document_id}.pdf",
#             self.processed_dir / document_id / "document.pdf",
#             self.processed_dir / document_id / "source.pdf"
#         ]

#         # Check exact path candidates
#         for path in candidate_paths:
#             if path.exists():
#                 return path

#         # Search for any PDF inside storage/raw or storage/processed/doc_id/
#         if self.raw_dir.exists():
#             for file in self.raw_dir.glob(f"*{document_id}*.pdf"):
#                 return file

#         doc_workspace = self.processed_dir / document_id
#         if doc_workspace.exists():
#             for file in doc_workspace.glob("*.pdf"):
#                 return file

#         raise DocumentNotFoundError(document_id)

#     async def build_structural_tree(self, document_id: str) -> Dict[str, Any]:
#         """Extracts complete document hierarchy including text, headings, 
#         bounding boxes, page numbers, extracted images with coordinates, 
#         and tabular matrix structures.
#         """
#         # 1. Locate PDF file
#         pdf_path = self._find_pdf_path(document_id)
#         logger.info(f"Located PDF file for structure extraction at: {pdf_path}")

#         # 2. Prepare output workspace
#         doc_output_dir = self.processed_dir / document_id
#         img_output_dir = doc_output_dir / "images"
#         img_output_dir.mkdir(parents=True, exist_ok=True)

#         try:
#             doc_fitz = fitz.open(str(pdf_path))
#             total_pages = len(doc_fitz)
            
#             # Extract Native Table of Contents
#             toc_raw = doc_fitz.get_toc()
#             table_of_contents = [
#                 {"level": item[0], "title": item[1], "page_number": item[2]}
#                 for item in toc_raw
#             ]

#             pages_data = []

#             # Process page by page with pdfplumber and PyMuPDF
#             with pdfplumber.open(str(pdf_path)) as doc_plumber:
#                 for page_idx in range(total_pages):
#                     page_num = page_idx + 1
#                     page_fitz = doc_fitz[page_idx]
#                     page_plumber = doc_plumber.pages[page_idx]
                    
#                     elements: List[Dict[str, Any]] = []
#                     headings: List[str] = []
#                     full_text_parts: List[str] = []

#                     # --- A. TABLES ---
#                     table_bboxes = []
#                     extracted_tables = page_plumber.find_tables()
#                     for t_idx, table_obj in enumerate(extracted_tables):
#                         bbox = list(table_obj.bbox)
#                         table_data = table_obj.extract()
                        
#                         table_bboxes.append(bbox)
#                         elements.append({
#                             "type": "table",
#                             "table_index": t_idx + 1,
#                             "bbox": [round(c, 2) for c in bbox],
#                             "row_count": len(table_data),
#                             "col_count": len(table_data[0]) if table_data else 0,
#                             "rows": table_data
#                         })

#                     # --- B. IMAGES & BBOX COORDINATES ---
#                     image_list = page_fitz.get_images(full=True)
#                     for img_idx, img_info in enumerate(image_list):
#                         xref = img_info[0]
#                         rects = page_fitz.get_image_rects(xref)
                        
#                         base_image = doc_fitz.extract_image(xref)
#                         image_bytes = base_image["image"]
#                         image_ext = base_image["ext"]
                        
#                         image_rel_path = f"images/page_{page_num}_img_{img_idx + 1}.{image_ext}"
#                         image_abs_path = doc_output_dir / image_rel_path
                        
#                         with open(image_abs_path, "wb") as f:
#                             f.write(image_bytes)

#                         for rect in rects:
#                             elements.append({
#                                 "type": "image",
#                                 "image_index": img_idx + 1,
#                                 "bbox": [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
#                                 "image_path": f"/storage/processed/{document_id}/{image_rel_path}",
#                                 "width": round(rect.width, 2),
#                                 "height": round(rect.height, 2)
#                             })

#                     # --- C. TEXT & HEADINGS ---
#                     blocks = page_fitz.get_text("dict", flags=fitz.TEXT_DEHYDRATE)["blocks"]
                    
#                     for block in blocks:
#                         if block.get("type") != 0:
#                             continue
                        
#                         block_bbox = [round(c, 2) for c in block["bbox"]]
                        
#                         if self._is_inside_any_table(block_bbox, table_bboxes):
#                             continue

#                         block_text = ""
#                         max_font_size = 0.0
#                         is_bold = False

#                         for line in block.get("lines", []):
#                             line_text = ""
#                             for span in line.get("spans", []):
#                                 line_text += span.get("text", "")
#                                 size = span.get("size", 0)
#                                 flags = span.get("flags", 0)
#                                 if size > max_font_size:
#                                     max_font_size = size
#                                 if flags & 2 or "bold" in span.get("font", "").lower():
#                                     is_bold = True
                            
#                             block_text += line_text + " "

#                         block_text = block_text.strip()
#                         if not block_text:
#                             continue

#                         element_type = "heading" if max_font_size > 14 or (max_font_size > 11 and is_bold) else "paragraph"
                        
#                         if element_type == "heading":
#                             headings.append(block_text)

#                         full_text_parts.append(block_text)
                        
#                         elements.append({
#                             "type": element_type,
#                             "text": block_text,
#                             "font_size": round(max_font_size, 1),
#                             "is_bold": is_bold,
#                             "bbox": block_bbox
#                         })

#                     # Sort elements by vertical position (top-to-bottom)
#                     elements.sort(key=lambda e: e["bbox"][1])

#                     pages_data.append({
#                         "page_number": page_num,
#                         "headings": headings,
#                         "elements_count": len(elements),
#                         "elements": elements,
#                         "full_text": "\n\n".join(full_text_parts)
#                     })

#             doc_fitz.close()

#             # 3. Output structural result
#             document_tree = {
#                 "document_id": document_id,
#                 "total_pages": total_pages,
#                 "has_native_toc": len(table_of_contents) > 0,
#                 "table_of_contents": table_of_contents,
#                 "pages": pages_data
#             }

#             tree_path = doc_output_dir / "document_tree.json"
#             with open(tree_path, "w", encoding="utf-8") as f:
#                 json.dump(document_tree, f, indent=4)

#             return document_tree

#         except Exception as e:
#             logger.error(f"Error building document tree for {document_id}: {str(e)}", exc_info=True)
#             raise ProcessingError(f"Failed to extract document structure: {str(e)}")

#     @staticmethod
#     def _is_inside_any_table(bbox: List[float], table_bboxes: List[List[float]]) -> bool:
#         x0, y0, x1, y1 = bbox
#         for tx0, ty0, tx1, ty1 in table_bboxes:
#             if x0 >= tx0 - 2 and x1 <= tx1 + 2 and y0 >= ty0 - 2 and y1 <= ty1 + 2:
#                 return True
#         return False











# import fitz  # PyMuPDF
# import pdfplumber
# import os
# import json
# from pathlib import Path
# from typing import Dict, Any, List
# from app.core.config import settings
# from app.core.logger import logger
# from app.core.exceptions import DocumentNotFoundError, ProcessingError

# class StructureService:
#     def __init__(self):
#         self.raw_dir = settings.STORAGE_RAW_DIR
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR

#     async def build_structural_tree(self, document_id: str) -> Dict[str, Any]:
#         """Extracts complete document hierarchy including text, headings, 
#         bounding boxes, page numbers, extracted images with coordinates, 
#         and tabular matrix structures.
#         """
#         # 1. Locate PDF source across possible directory layouts
#         pdf_path = None
        
#         # Check nested structure: storage/raw/{document_id}/original.pdf
#         nested_pdf = self.raw_dir / document_id / "original.pdf"
#         if nested_pdf.exists():
#             pdf_path = nested_pdf
#         else:
#             # Check flat structure: storage/raw/{document_id}.pdf
#             flat_pdf = self.raw_dir / f"{document_id}.pdf"
#             if flat_pdf.exists():
#                 pdf_path = flat_pdf
#             else:
#                 # Fallback search inside processed directory workspace
#                 workspace = self.processed_dir / document_id
#                 pdf_files = list(workspace.glob("*.pdf")) if workspace.exists() else []
#                 if pdf_files:
#                     pdf_path = pdf_files[0]

#         if not pdf_path or not pdf_path.exists():
#             raise DocumentNotFoundError(document_id)

#         # 2. Setup output directories for saved assets (images)
#         doc_output_dir = self.processed_dir / document_id
#         img_output_dir = doc_output_dir / "images"
#         img_output_dir.mkdir(parents=True, exist_ok=True)

#         try:
#             doc_fitz = fitz.open(str(pdf_path))
#             total_pages = len(doc_fitz)
            
#             # Extract Native Table of Contents if available
#             toc_raw = doc_fitz.get_toc()
#             table_of_contents = [
#                 {"level": item[0], "title": item[1], "page_number": item[2]}
#                 for item in toc_raw
#             ]

#             pages_data = []

#             # Open with pdfplumber for high-precision table extraction
#             with pdfplumber.open(str(pdf_path)) as doc_plumber:
#                 for page_idx in range(total_pages):
#                     page_num = page_idx + 1
#                     page_fitz = doc_fitz[page_idx]
#                     page_plumber = doc_plumber.pages[page_idx]
                    
#                     elements: List[Dict[str, Any]] = []
#                     headings: List[str] = []
#                     full_text_parts: List[str] = []

#                     # -------------------------------------------------
#                     # A. EXTRACT TABLES (via pdfplumber)
#                     # -------------------------------------------------
#                     table_bboxes = []
#                     extracted_tables = page_plumber.find_tables()
#                     for t_idx, table_obj in enumerate(extracted_tables):
#                         bbox = list(table_obj.bbox)  # [x0, top, x1, bottom]
#                         table_data = table_obj.extract()
                        
#                         table_bboxes.append(bbox)
#                         elements.append({
#                             "type": "table",
#                             "table_index": t_idx + 1,
#                             "bbox": [round(c, 2) for c in bbox],
#                             "row_count": len(table_data),
#                             "col_count": len(table_data[0]) if table_data else 0,
#                             "rows": table_data
#                         })

#                     # -------------------------------------------------
#                     # B. EXTRACT IMAGES & COORDINATES (via PyMuPDF)
#                     # -------------------------------------------------
#                     image_list = page_fitz.get_images(full=True)
#                     for img_idx, img_info in enumerate(image_list):
#                         xref = img_info[0]
#                         rects = page_fitz.get_image_rects(xref)
                        
#                         base_image = doc_fitz.extract_image(xref)
#                         image_bytes = base_image["image"]
#                         image_ext = base_image["ext"]
                        
#                         image_rel_path = f"images/page_{page_num}_img_{img_idx + 1}.{image_ext}"
#                         image_abs_path = doc_output_dir / image_rel_path
                        
#                         with open(image_abs_path, "wb") as f:
#                             f.write(image_bytes)

#                         for rect in rects:
#                             elements.append({
#                                 "type": "image",
#                                 "image_index": img_idx + 1,
#                                 "bbox": [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
#                                 "image_path": f"/storage/processed/{document_id}/{image_rel_path}",
#                                 "width": round(rect.width, 2),
#                                 "height": round(rect.height, 2)
#                             })

#                     # -------------------------------------------------
#                     # C. EXTRACT TEXT / HEADINGS / PARAGRAPHS
#                     # -------------------------------------------------
#                     blocks = page_fitz.get_text("dict", flags=fitz.TEXT_DEHYDRATE)["blocks"]
                    
#                     for block in blocks:
#                         if block.get("type") != 0:
#                             continue
                        
#                         block_bbox = [round(c, 2) for c in block["bbox"]]
                        
#                         if self._is_inside_any_table(block_bbox, table_bboxes):
#                             continue

#                         block_text = ""
#                         max_font_size = 0.0
#                         is_bold = False

#                         for line in block.get("lines", []):
#                             line_text = ""
#                             for span in line.get("spans", []):
#                                 line_text += span.get("text", "")
#                                 size = span.get("size", 0)
#                                 flags = span.get("flags", 0)
#                                 if size > max_font_size:
#                                     max_font_size = size
#                                 if flags & 2 or "bold" in span.get("font", "").lower():
#                                     is_bold = True
                            
#                             block_text += line_text + " "

#                         block_text = block_text.strip()
#                         if not block_text:
#                             continue

#                         element_type = "heading" if max_font_size > 14 or (max_font_size > 11 and is_bold) else "paragraph"
                        
#                         if element_type == "heading":
#                             headings.append(block_text)

#                         full_text_parts.append(block_text)
                        
#                         elements.append({
#                             "type": element_type,
#                             "text": block_text,
#                             "font_size": round(max_font_size, 1),
#                             "is_bold": is_bold,
#                             "bbox": block_bbox
#                         })

#                     elements.sort(key=lambda e: e["bbox"][1])

#                     pages_data.append({
#                         "page_number": page_num,
#                         "headings": headings,
#                         "elements_count": len(elements),
#                         "elements": elements,
#                         "full_text": "\n\n".join(full_text_parts)
#                     })

#             doc_fitz.close()

#             document_tree = {
#                 "document_id": document_id,
#                 "total_pages": total_pages,
#                 "has_native_toc": len(table_of_contents) > 0,
#                 "table_of_contents": table_of_contents,
#                 "pages": pages_data
#             }

#             tree_path = doc_output_dir / "document_tree.json"
#             with open(tree_path, "w", encoding="utf-8") as f:
#                 json.dump(document_tree, f, indent=4)

#             logger.info(f"Successfully processed document structure for {document_id}")
#             return document_tree

#         except Exception as e:
#             logger.error(f"Error building document tree for {document_id}: {str(e)}", exc_info=True)
#             raise ProcessingError(f"Failed to extract document structure: {str(e)}")

#     @staticmethod
#     def _is_inside_any_table(bbox: List[float], table_bboxes: List[List[float]]) -> bool:
#         x0, y0, x1, y1 = bbox
#         for tx0, ty0, tx1, ty1 in table_bboxes:
#             if x0 >= tx0 - 2 and x1 <= tx1 + 2 and y0 >= ty0 - 2 and y1 <= ty1 + 2:
#                 return True
#         return False














# import fitz  # PyMuPDF
# import pdfplumber
# import os
# import json
# from pathlib import Path
# from typing import Dict, Any, List
# from app.core.config import settings
# from app.core.logger import logger
# from app.core.exceptions import DocumentNotFoundError, ProcessingError

# class StructureService:
#     def __init__(self):
#         self.raw_dir = settings.STORAGE_RAW_DIR
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR

#     async def build_structural_tree(self, document_id: str) -> Dict[str, Any]:
#         """Extracts complete document hierarchy including text, headings, 
#         bounding boxes, page numbers, extracted images with coordinates, 
#         and tabular matrix structures.
#         """
#         # 1. Locate PDF source matching storage schema: storage/raw/{document_id}/original.pdf
#         pdf_path = self.raw_dir / document_id / "original.pdf"
#         if not pdf_path.exists():
#             alt_pdf_path = self.raw_dir / f"{document_id}.pdf"
#             if alt_pdf_path.exists():
#                 pdf_path = alt_pdf_path
#             else:
#                 workspace = self.processed_dir / document_id
#                 pdf_files = list(workspace.glob("*.pdf")) if workspace.exists() else []
#                 if pdf_files:
#                     pdf_path = pdf_files[0]
#                 else:
#                     raise DocumentNotFoundError(document_id)

#         # 2. Setup output directories for saved assets (images)
#         doc_output_dir = self.processed_dir / document_id
#         img_output_dir = doc_output_dir / "images"
#         img_output_dir.mkdir(parents=True, exist_ok=True)

#         try:
#             doc_fitz = fitz.open(str(pdf_path))
#             total_pages = len(doc_fitz)
            
#             # Extract Native Table of Contents if available
#             toc_raw = doc_fitz.get_toc()
#             table_of_contents = [
#                 {"level": item[0], "title": item[1], "page_number": item[2]}
#                 for item in toc_raw
#             ]

#             pages_data = []

#             # Open with pdfplumber for high-precision table extraction
#             with pdfplumber.open(str(pdf_path)) as doc_plumber:
#                 for page_idx in range(total_pages):
#                     page_num = page_idx + 1
#                     page_fitz = doc_fitz[page_idx]
#                     page_plumber = doc_plumber.pages[page_idx]
                    
#                     elements: List[Dict[str, Any]] = []
#                     headings: List[str] = []
#                     full_text_parts: List[str] = []

#                     # -------------------------------------------------
#                     # A. EXTRACT TABLES (via pdfplumber)
#                     # -------------------------------------------------
#                     table_bboxes = []
#                     extracted_tables = page_plumber.find_tables()
#                     for t_idx, table_obj in enumerate(extracted_tables):
#                         bbox = list(table_obj.bbox)  # [x0, top, x1, bottom]
#                         table_data = table_obj.extract()
                        
#                         table_bboxes.append(bbox)
#                         elements.append({
#                             "type": "table",
#                             "table_index": t_idx + 1,
#                             "bbox": [round(c, 2) for c in bbox],
#                             "row_count": len(table_data),
#                             "col_count": len(table_data[0]) if table_data else 0,
#                             "rows": table_data
#                         })

#                     # -------------------------------------------------
#                     # B. EXTRACT IMAGES & COORDINATES (via PyMuPDF)
#                     # -------------------------------------------------
#                     image_list = page_fitz.get_images(full=True)
#                     for img_idx, img_info in enumerate(image_list):
#                         xref = img_info[0]
#                         rects = page_fitz.get_image_rects(xref)
                        
#                         base_image = doc_fitz.extract_image(xref)
#                         image_bytes = base_image["image"]
#                         image_ext = base_image["ext"]
                        
#                         image_rel_path = f"images/page_{page_num}_img_{img_idx + 1}.{image_ext}"
#                         image_abs_path = doc_output_dir / image_rel_path
                        
#                         with open(image_abs_path, "wb") as f:
#                             f.write(image_bytes)

#                         for rect in rects:
#                             elements.append({
#                                 "type": "image",
#                                 "image_index": img_idx + 1,
#                                 "bbox": [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
#                                 "image_path": f"/storage/processed/{document_id}/{image_rel_path}",
#                                 "width": round(rect.width, 2),
#                                 "height": round(rect.height, 2)
#                             })

#                     # -------------------------------------------------
#                     # C. EXTRACT TEXT / HEADINGS / PARAGRAPHS
#                     # -------------------------------------------------
#                     blocks = page_fitz.get_text("dict")["blocks"]
                    
#                     for block in blocks:
#                         if block.get("type") != 0:
#                             continue
                        
#                         block_bbox = [round(c, 2) for c in block["bbox"]]
                        
#                         if self._is_inside_any_table(block_bbox, table_bboxes):
#                             continue

#                         block_text = ""
#                         max_font_size = 0.0
#                         is_bold = False

#                         for line in block.get("lines", []):
#                             line_text = ""
#                             for span in line.get("spans", []):
#                                 line_text += span.get("text", "")
#                                 size = span.get("size", 0)
#                                 flags = span.get("flags", 0)
#                                 if size > max_font_size:
#                                     max_font_size = size
#                                 if flags & 2 or "bold" in span.get("font", "").lower():
#                                     is_bold = True
                            
#                             block_text += line_text + " "

#                         block_text = block_text.strip()
#                         if not block_text:
#                             continue

#                         element_type = "heading" if max_font_size > 14 or (max_font_size > 11 and is_bold) else "paragraph"
                        
#                         if element_type == "heading":
#                             headings.append(block_text)

#                         full_text_parts.append(block_text)
                        
#                         elements.append({
#                             "type": element_type,
#                             "text": block_text,
#                             "font_size": round(max_font_size, 1),
#                             "is_bold": is_bold,
#                             "bbox": block_bbox
#                         })

#                     elements.sort(key=lambda e: e["bbox"][1])

#                     pages_data.append({
#                         "page_number": page_num,
#                         "headings": headings,
#                         "elements_count": len(elements),
#                         "elements": elements,
#                         "full_text": "\n\n".join(full_text_parts)
#                     })

#             doc_fitz.close()

#             document_tree = {
#                 "document_id": document_id,
#                 "total_pages": total_pages,
#                 "has_native_toc": len(table_of_contents) > 0,
#                 "table_of_contents": table_of_contents,
#                 "pages": pages_data
#             }

#             tree_path = doc_output_dir / "document_tree.json"
#             with open(tree_path, "w", encoding="utf-8") as f:
#                 json.dump(document_tree, f, indent=4)

#             logger.info(f"Successfully processed document structure for {document_id}")
#             return document_tree

#         except Exception as e:
#             logger.error(f"Error building document tree for {document_id}: {str(e)}", exc_info=True)
#             raise ProcessingError(f"Failed to extract document structure: {str(e)}")

#     @staticmethod
#     def _is_inside_any_table(bbox: List[float], table_bboxes: List[List[float]]) -> bool:
#         x0, y0, x1, y1 = bbox
#         for tx0, ty0, tx1, ty1 in table_bboxes:
#             if x0 >= tx0 - 2 and x1 <= tx1 + 2 and y0 >= ty0 - 2 and y1 <= ty1 + 2:
#                 return True
#         return False






# import io
# import json
# import re
# from pathlib import Path
# from typing import Any, Dict, List

# import pymupdf as fitz  # Future-proofed import alias
# import pdfplumber
# from PIL import Image
# import pytesseract
# # Gracefully handle Tesseract dependency
# try:
#     import pytesseract
#     TESSERACT_AVAILABLE = True
# except ImportError:
#     TESSERACT_AVAILABLE = False

# from app.core.config import settings
# from app.core.exceptions import DocumentNotFoundError, ProcessingError
# from app.core.logger import logger


# class StructureService:
#     def __init__(self):
#         self.raw_dir = settings.STORAGE_RAW_DIR
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR

#         # OCR configuration for full-page fallback only
#         self.tesseract_config = "--oem 3 --psm 6 -c preserve_interword_spaces=1"

#     ###########################################################################
#     # PART 1: HELPERS & INITIALIZATION
#     ###########################################################################

#     def _locate_pdf(self, document_id: str) -> Path:
#         pdf_path = self.raw_dir / document_id / "original.pdf"
#         if pdf_path.exists():
#             return pdf_path
#         alt = self.raw_dir / f"{document_id}.pdf"
#         if alt.exists():
#             return alt
#         processed = self.processed_dir / document_id
#         if processed.exists():
#             pdfs = list(processed.glob("*.pdf"))
#             if pdfs:
#                 return pdfs[0]
#         raise DocumentNotFoundError(document_id)

#     def _create_output_directories(self, document_id: str) -> Dict[str, Path]:
#         root = self.processed_dir / document_id
#         folders = {
#             "root": root,
#             "images": root / "images",
#             "tables": root / "tables"
#         }
#         for folder in folders.values():
#             folder.mkdir(parents=True, exist_ok=True)
#         return folders

#     def _bbox(self, bbox) -> List[float]:
#         return [round(float(x), 2) for x in bbox]

#     def _inside_table(self, bbox: List[float], table_boxes: List[List[float]]) -> bool:
#         x0, y0, x1, y1 = bbox
#         for tx0, ty0, tx1, ty1 in table_boxes:
#             if x0 >= tx0 - 2 and x1 <= tx1 + 2 and y0 >= ty0 - 2 and y1 <= ty1 + 2:
#                 return True
#         return False

#     def _save_image(self, image_bytes: bytes, image_path: Path):
#         with open(image_path, "wb") as f:
#             f.write(image_bytes)

#     def _ocr_full_page(self, page: fitz.Page) -> str:
#         """Fallback OCR invoked ONLY if Tesseract is installed and configured."""
#         if not TESSERACT_AVAILABLE:
#             return ""
            
#         try:
#             pix = page.get_pixmap(dpi=300)
#             image = Image.open(io.BytesIO(pix.tobytes("png")))
#             text = pytesseract.image_to_string(image, config=self.tesseract_config)
#             return text.strip()
#         except Exception as e:
#             logger.warning(f"Full page OCR failed or Tesseract executable not found: {str(e)}")
#             return ""

#     def _heading_level(self, font_size: float, is_bold: bool) -> int:
#         """Restored original robust logic: Large fonts OR medium fonts that are bold."""
#         if font_size > 14.0: return 1         # Primary Heading (e.g., Chapter)
#         if font_size > 11.0 and is_bold: return 2 # Secondary Heading (e.g., Section)
#         return 0 # Not a heading

#     def _sort_reading_order(self, elements: List[Dict]) -> List[Dict]:
#         """Sorts top-to-bottom, left-to-right supporting multi-column layouts."""
#         return sorted(
#             elements,
#             key=lambda x: (
#                 round(x["bbox"][1] / 10),
#                 round(x["bbox"][0])
#             ),
#         )

#     ###########################################################################
#     # PART 2: GRAPH BUILDING & RELATIONAL POINTERS
#     ###########################################################################

#     def _build_document_graph_and_pointers(self, global_elements: List[Dict]) -> Dict[str, Any]:
#         """
#         Takes the flat, sequenced list of all elements in the entire book and builds
#         a highly relational tree with parent, child, sibling, and continuity pointers.
#         """
#         document_graph = {"type": "document", "title": "Root", "children": []}
#         stack_nodes = [{"level": 0, "node": document_graph, "element_id": "root"}]

#         # 1. First Pass: Previous/Next Pointers & Paragraph Continuity
#         for i, el in enumerate(global_elements):
#             el["previous_element_id"] = global_elements[i-1]["element_id"] if i > 0 else None
#             el["next_element_id"] = global_elements[i+1]["element_id"] if i < len(global_elements)-1 else None
            
#             # Cross-page paragraph continuity
#             if i < len(global_elements)-1:
#                 next_el = global_elements[i+1]
#                 if el["type"] == "paragraph" and next_el["type"] == "paragraph":
#                     # If this paragraph ends without terminal punctuation and next starts lowercase
#                     if not re.search(r'[.?!:]$', el.get("text", "").strip()) and re.match(r'^[a-z]', next_el.get("text", "").strip()):
#                         el["continues_in_element_id"] = next_el["element_id"]
#                         next_el["continued_from_element_id"] = el["element_id"]

#         # 2. Second Pass: Hierarchy, Parent/Child, and Captions
#         for i, el in enumerate(global_elements):
#             el_type = el["type"]
#             font_size = el.get("font_size", 12.0)
#             is_bold = el.get("is_bold", False)

#             # Handle Heading Hierarchy
#             h_level = self._heading_level(font_size, is_bold)
#             if el_type == "heading" or h_level > 0:
#                 el["type"] = "heading"
#                 el["heading_level"] = h_level
                
#                 # Pop stack until we find a parent level smaller than current
#                 while len(stack_nodes) > 1 and stack_nodes[-1]["level"] >= h_level:
#                     stack_nodes.pop()
                    
#                 parent_node = stack_nodes[-1]
#                 el["parent_element_id"] = parent_node["element_id"]
                
#                 # Build tree node
#                 new_node = {
#                     "element_id": el["element_id"],
#                     "type": "heading",
#                     "text": el.get("text", ""),
#                     "level": h_level,
#                     "children": []
#                 }
#                 parent_node["node"]["children"].append(new_node)
#                 stack_nodes.append({"level": h_level, "node": new_node, "element_id": el["element_id"]})
                
#             else:
#                 # Assign non-headings to the current active heading section
#                 parent_node = stack_nodes[-1]
#                 el["parent_element_id"] = parent_node["element_id"]
#                 parent_node["node"]["children"].append({
#                     "element_id": el["element_id"],
#                     "type": el_type,
#                     "text": el.get("text", f"[{el_type.upper()}]")
#                 })

#             # Assign section path
#             el["section_path"] = [node["node"]["text"] for node in stack_nodes if node["level"] > 0]

#             # Link Captions to nearest Image or Table
#             if el_type == "caption":
#                 # Look backwards up to 3 elements for an image or table
#                 for j in range(i-1, max(-1, i-4), -1):
#                     prev_el = global_elements[j]
#                     if prev_el["type"] in ["image", "table"]:
#                         el["target_element_id"] = prev_el["element_id"]
#                         prev_el["caption_element_id"] = el["element_id"]
#                         break

#         return document_graph

#     ###########################################################################
#     # PART 3: MASTER EXTRACTION ORCHESTRATOR
#     ###########################################################################

#     async def build_structural_tree(self, document_id: str) -> Dict[str, Any]:
#         pdf_path = self._locate_pdf(document_id)
#         folders = self._create_output_directories(document_id)

#         try:
#             logger.info(f"Extracting highly relational document structure for {document_id}")
#             doc_fitz = fitz.open(str(pdf_path))
#             total_pages = len(doc_fitz)

#             # Native TOC
#             toc_raw = doc_fitz.get_toc()
#             table_of_contents = [
#                 {"level": item[0], "title": item[1].strip(), "page_number": item[2]}
#                 for item in toc_raw
#             ]

#             global_elements = []  # Flat linear sequence of entire document
#             pages_data = []       # Backward compatible page boundaries
#             global_sequence_index = 1

#             with pdfplumber.open(str(pdf_path)) as doc_plumber:
#                 for page_idx in range(total_pages):
#                     page_num = page_idx + 1
#                     page_fitz = doc_fitz[page_idx]
#                     page_plumber = doc_plumber.pages[page_idx]

#                     raw_page_elements = []
#                     table_bboxes = []

#                     # 1. TABLES
#                     extracted_tables = page_plumber.find_tables()
#                     for t_idx, table_obj in enumerate(extracted_tables):
#                         bbox = self._bbox(table_obj.bbox)
#                         table_data = table_obj.extract()
#                         table_bboxes.append(bbox)
                        
#                         raw_page_elements.append({
#                             "type": "table",
#                             "table_index": t_idx + 1,
#                             "bbox": bbox,
#                             "row_count": len(table_data),
#                             "col_count": len(table_data[0]) if table_data else 0,
#                             "rows": table_data
#                         })

#                     # 2. IMAGES (No OCR)
#                     image_list = page_fitz.get_images(full=True)
#                     for img_idx, img_info in enumerate(image_list):
#                         xref = img_info[0]
#                         rects = page_fitz.get_image_rects(xref)
                        
#                         base_image = doc_fitz.extract_image(xref)
#                         image_bytes = base_image["image"]
#                         image_ext = base_image["ext"]
#                         image_filename = f"page_{page_num}_img_{img_idx + 1}.{image_ext}"
#                         image_path = folders["images"] / image_filename
                        
#                         self._save_image(image_bytes, image_path)

#                         for rect in rects:
#                             raw_page_elements.append({
#                                 "type": "image",
#                                 "image_index": img_idx + 1,
#                                 "xref": xref,
#                                 "bbox": self._bbox([rect.x0, rect.y0, rect.x1, rect.y1]),
#                                 "image_path": f"/storage/processed/{document_id}/images/{image_filename}",
#                                 "width": round(rect.width, 2),
#                                 "height": round(rect.height, 2)
#                             })

#                     # 3. TEXT & HEADINGS
#                     blocks = page_fitz.get_text("dict").get("blocks", [])
                    
#                     if not blocks:
#                         page_text = self._ocr_full_page(page_fitz)
                        
#                         if page_text:
#                             raw_page_elements.append({
#                                 "type": "paragraph",
#                                 "text": page_text,
#                                 "font_size": 12.0,
#                                 "is_bold": False,
#                                 "bbox": self._bbox([0, 0, page_fitz.rect.width, page_fitz.rect.height])
#                             })
#                         else:
#                             # 🚨 ENTERPRISE SAFEGUARD: Never discard a page. Insert a placeholder.
#                             logger.warning(f"No extractable text found on page {page_num}. Marking as scanned_page for future processing.")
#                             raw_page_elements.append({
#                                 "type": "scanned_page",
#                                 "text": "",
#                                 "font_size": 0,
#                                 "is_bold": False,
#                                 "bbox": self._bbox([0, 0, page_fitz.rect.width, page_fitz.rect.height]),
#                                 "requires_ocr": True
#                             })
#                     else:
#                         for block in blocks:
#                             if block.get("type") != 0: 
#                                 continue
                            
#                             block_bbox = self._bbox(block["bbox"])
#                             if self._inside_table(block_bbox, table_bboxes):
#                                 continue

#                             block_text = ""
#                             max_font_size = 0.0
#                             is_bold = False

#                             for line in block.get("lines", []):
#                                 for span in line.get("spans", []):
#                                     block_text += span.get("text", "")
#                                     size = span.get("size", 0)
#                                     if size > max_font_size: max_font_size = size
#                                     flags = span.get("flags", 0)
#                                     if (flags & 2) or "bold" in span.get("font", "").lower():
#                                         is_bold = True
#                                 block_text += " "

#                             block_text = block_text.strip()
#                             if not block_text:
#                                 continue

#                             # Pre-classification of element type using robust logic
#                             element_type = "heading" if self._heading_level(max_font_size, is_bold) > 0 else "paragraph"
#                             if re.match(r"^(fig\.?|figure|table|chart)\s*\d+", block_text, re.IGNORECASE):
#                                 element_type = "caption"

#                             raw_page_elements.append({
#                                 "type": element_type,
#                                 "text": block_text,
#                                 "font_size": round(max_font_size, 1),
#                                 "is_bold": is_bold,
#                                 "bbox": block_bbox
#                             })

#                     # 4. PAGE-LEVEL SORTING & ID ASSIGNMENT
#                     sorted_page_elements = self._sort_reading_order(raw_page_elements)
                    
#                     for el in sorted_page_elements:
#                         el_type = el["type"]
#                         el["page_number"] = page_num
#                         el["element_id"] = f"{document_id}_p{page_num}_{el_type}_{global_sequence_index}"
#                         el["reading_sequence"] = global_sequence_index
#                         global_elements.append(el)
#                         global_sequence_index += 1

#             doc_fitz.close()

#             # ---------------------------------------------------------
#             # 5. CROSS-DOCUMENT GRAPH & POINTER RESOLUTION
#             # ---------------------------------------------------------
#             document_graph = self._build_document_graph_and_pointers(global_elements)

#             # Re-group augmented elements back into pages for backward compatibility
#             # Ensure every single page is explicitly represented to preserve pagination numbering.
#             for page_num in range(1, total_pages + 1):
#                 page_elems = [e for e in global_elements if e.get("page_number") == page_num]
                
#                 page_headings = [e["text"] for e in page_elems if e.get("type") == "heading"]
#                 full_text_str = "\n\n".join([e.get("text", "") for e in page_elems if "text" in e])

#                 pages_data.append({
#                     "page_number": page_num,
#                     "headings": page_headings,
#                     "elements_count": len(page_elems),
#                     "elements": page_elems,
#                     "full_text": full_text_str
#                 })

#             # ---------------------------------------------------------
#             # 6. ASSEMBLE FINAL JSON
#             # ---------------------------------------------------------
#             document_tree = {
#                 "document_id": document_id,
#                 "total_pages": total_pages,
#                 "has_native_toc": len(table_of_contents) > 0,
#                 "table_of_contents": table_of_contents,
#                 "document_graph": document_graph,
#                 "pages": pages_data
#             }

#             tree_path = folders["root"] / "document_tree.json"
#             with open(tree_path, "w", encoding="utf-8") as f:
#                 json.dump(document_tree, f, indent=4, ensure_ascii=False)

#             logger.info(f"Successfully processed highly relational document structure for {document_id}")
#             return document_tree

#         except Exception as e:
#             logger.error(f"Error building relational document tree for {document_id}: {str(e)}", exc_info=True)
#             raise ProcessingError(f"Failed to extract document structure: {str(e)}")





# import io
# import json
# import re
# from pathlib import Path
# from typing import Any, Dict, List

# import pymupdf as fitz  # Future-proofed import alias
# import pdfplumber
# from PIL import Image

# # Gracefully handle Tesseract dependency
# try:
#     import pytesseract
#     TESSERACT_AVAILABLE = True
# except ImportError:
#     TESSERACT_AVAILABLE = False

# from app.core.config import settings
# from app.core.exceptions import DocumentNotFoundError, ProcessingError
# from app.core.logger import logger


# class StructureService:
#     def __init__(self):
#         self.raw_dir = settings.STORAGE_RAW_DIR
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR
#         # OCR configuration for full-page fallback only
#         self.tesseract_config = "--oem 3 --psm 6 -c preserve_interword_spaces=1"

#     ###########################################################################
#     # PART 1: HELPERS & INITIALIZATION
#     ###########################################################################

#     def _locate_pdf(self, document_id: str) -> Path:
#         pdf_path = self.raw_dir / document_id / "original.pdf"
#         if pdf_path.exists():
#             return pdf_path
#         alt = self.raw_dir / f"{document_id}.pdf"
#         if alt.exists():
#             return alt
#         processed = self.processed_dir / document_id
#         if processed.exists():
#             pdfs = list(processed.glob("*.pdf"))
#             if pdfs:
#                 return pdfs[0]
#         raise DocumentNotFoundError(document_id)

#     def _create_output_directories(self, document_id: str) -> Dict[str, Path]:
#         root = self.processed_dir / document_id
#         folders = {
#             "root": root,
#             "images": root / "images",
#             "tables": root / "tables"
#         }
#         for folder in folders.values():
#             folder.mkdir(parents=True, exist_ok=True)
#         return folders

#     def _bbox(self, bbox) -> List[float]:
#         return [round(float(x), 2) for x in bbox]

#     def _inside_table(self, bbox: List[float], table_boxes: List[List[float]]) -> bool:
#         x0, y0, x1, y1 = bbox
#         for tx0, ty0, tx1, ty1 in table_boxes:
#             # Allow 2px tolerance for layout drift
#             if x0 >= tx0 - 2 and x1 <= tx1 + 2 and y0 >= ty0 - 2 and y1 <= ty1 + 2:
#                 return True
#         return False

#     def _save_image(self, image_bytes: bytes, image_path: Path):
#         with open(image_path, "wb") as f:
#             f.write(image_bytes)

#     def _table_to_markdown(self, table_data: List[List[str]]) -> str:
#         """Converts raw table grids into strict Markdown for zero-hallucination LLM extraction."""
#         if not table_data or not table_data[0]:
#             return ""
        
#         # Clean nulls/newlines
#         cleaned_table = [
#             [" ".join(str(cell).split()) if cell else "" for cell in row]
#             for row in table_data
#         ]
        
#         headers = cleaned_table[0]
#         md = f"| {' | '.join(headers)} |\n"
#         md += f"|{'|'.join(['---'] * len(headers))}|\n"
        
#         for row in cleaned_table[1:]:
#             # Pad row if shorter than headers
#             row += [""] * (len(headers) - len(row))
#             md += f"| {' | '.join(row[:len(headers)])} |\n"
            
#         return md

#     def _ocr_full_page(self, page: fitz.Page) -> str:
#         """Fallback OCR invoked ONLY if Tesseract is installed and configured."""
#         if not TESSERACT_AVAILABLE:
#             return ""
            
#         try:
#             pix = page.get_pixmap(dpi=300)
#             image = Image.open(io.BytesIO(pix.tobytes("png")))
#             text = pytesseract.image_to_string(image, config=self.tesseract_config)
#             return text.strip()
#         except Exception as e:
#             logger.warning(f"Full page OCR failed or Tesseract executable not found: {str(e)}")
#             return ""

#     def _heading_level(self, font_size: float, is_bold: bool) -> int:
#         """Robust structural logic: Large fonts OR medium fonts that are bold."""
#         if font_size > 14.0: return 1         # Primary Heading (e.g., Chapter/Major Food Item)
#         if font_size > 11.0 and is_bold: return 2 # Secondary Heading (e.g., Evaluation Category)
#         return 0 # Not a heading

#     def _sort_reading_order(self, elements: List[Dict]) -> List[Dict]:
#         """Sorts top-to-bottom, left-to-right supporting multi-column layouts."""
#         return sorted(
#             elements,
#             key=lambda x: (
#                 round(x["bbox"][1] / 10),
#                 round(x["bbox"][0])
#             ),
#         )

#     ###########################################################################
#     # PART 2: GRAPH BUILDING & RELATIONAL POINTERS (Anti-Hallucination Core)
#     ###########################################################################

#     def _build_document_graph_and_pointers(self, global_elements: List[Dict]) -> Dict[str, Any]:
#         """
#         Builds a highly relational tree. Stamping every table/paragraph with its 
#         parent heading lineage prevents floating attribute hallucinations.
#         """
#         document_graph = {"type": "document", "title": "Root", "children": []}
#         stack_nodes = [{"level": 0, "node": document_graph, "element_id": "root"}]

#         # 1. First Pass: Previous/Next Pointers & Paragraph Continuity
#         for i, el in enumerate(global_elements):
#             el["previous_element_id"] = global_elements[i-1]["element_id"] if i > 0 else None
#             el["next_element_id"] = global_elements[i+1]["element_id"] if i < len(global_elements)-1 else None
            
#             # Cross-page paragraph continuity
#             if i < len(global_elements)-1:
#                 next_el = global_elements[i+1]
#                 if el["type"] == "paragraph" and next_el["type"] == "paragraph":
#                     # If this paragraph ends without terminal punctuation and next starts lowercase
#                     if not re.search(r'[.?!:]$', el.get("text", "").strip()) and re.match(r'^[a-z]', next_el.get("text", "").strip()):
#                         el["continues_in_element_id"] = next_el["element_id"]
#                         next_el["continued_from_element_id"] = el["element_id"]

#         # 2. Second Pass: Hierarchy, Breadcrumbs, and Parent/Child
#         for i, el in enumerate(global_elements):
#             el_type = el["type"]
#             font_size = el.get("font_size", 12.0)
#             is_bold = el.get("is_bold", False)

#             # Handle Heading Hierarchy
#             h_level = self._heading_level(font_size, is_bold)
#             if el_type == "heading" or h_level > 0:
#                 el["type"] = "heading"
#                 el["heading_level"] = h_level
                
#                 # Pop stack until we find a parent level smaller than current
#                 while len(stack_nodes) > 1 and stack_nodes[-1]["level"] >= h_level:
#                     stack_nodes.pop()
                    
#                 parent_node = stack_nodes[-1]
#                 el["parent_element_id"] = parent_node["element_id"]
                
#                 # Build tree node
#                 new_node = {
#                     "element_id": el["element_id"],
#                     "type": "heading",
#                     "text": el.get("text", ""),
#                     "level": h_level,
#                     "children": []
#                 }
#                 parent_node["node"]["children"].append(new_node)
#                 stack_nodes.append({"level": h_level, "node": new_node, "element_id": el["element_id"]})
                
#             else:
#                 # Assign non-headings to the current active heading section
#                 parent_node = stack_nodes[-1]
#                 el["parent_element_id"] = parent_node["element_id"]
#                 parent_node["node"]["children"].append({
#                     "element_id": el["element_id"],
#                     "type": el_type,
#                     "text": el.get("text", f"[{el_type.upper()}]")
#                 })

#             # Assign section path and explicit string breadcrumb for the LLM
#             el["section_path"] = [node["node"]["text"] for node in stack_nodes if node["level"] > 0]
#             el["context_breadcrumb"] = " > ".join(el["section_path"]) if el["section_path"] else "Root"

#             # Link Captions to nearest Image or Table
#             if el_type == "caption":
#                 # Look backwards up to 3 elements for an image or table
#                 for j in range(i-1, max(-1, i-4), -1):
#                     prev_el = global_elements[j]
#                     if prev_el["type"] in ["image", "table"]:
#                         el["target_element_id"] = prev_el["element_id"]
#                         prev_el["caption_element_id"] = el["element_id"]
#                         break

#         return document_graph

#     ###########################################################################
#     # PART 3: MASTER EXTRACTION ORCHESTRATOR
#     ###########################################################################

#     async def build_structural_tree(self, document_id: str) -> Dict[str, Any]:
#         pdf_path = self._locate_pdf(document_id)
#         folders = self._create_output_directories(document_id)

#         try:
#             logger.info(f"Extracting highly relational document structure for {document_id}")
#             doc_fitz = fitz.open(str(pdf_path))
#             total_pages = len(doc_fitz)

#             # Native TOC
#             toc_raw = doc_fitz.get_toc()
#             table_of_contents = [
#                 {"level": item[0], "title": item[1].strip(), "page_number": item[2]}
#                 for item in toc_raw
#             ]

#             global_elements = []  # Flat linear sequence of entire document
#             pages_data = []       # Backward compatible page boundaries
#             global_sequence_index = 1

#             with pdfplumber.open(str(pdf_path)) as doc_plumber:
#                 for page_idx in range(total_pages):
#                     page_num = page_idx + 1
#                     page_fitz = doc_fitz[page_idx]
#                     page_plumber = doc_plumber.pages[page_idx]

#                     raw_page_elements = []
#                     table_bboxes = []

#                     # 1. TABLES (Extracted as raw arrays AND Markdown strings)
#                     extracted_tables = page_plumber.find_tables()
#                     for t_idx, table_obj in enumerate(extracted_tables):
#                         bbox = self._bbox(table_obj.bbox)
#                         table_data = table_obj.extract()
#                         table_bboxes.append(bbox)
                        
#                         raw_page_elements.append({
#                             "type": "table",
#                             "table_index": t_idx + 1,
#                             "bbox": bbox,
#                             "row_count": len(table_data),
#                             "col_count": len(table_data[0]) if table_data else 0,
#                             "rows": table_data,
#                             "markdown": self._table_to_markdown(table_data)  # Crucial for LLM understanding
#                         })

#                     # 2. IMAGES (No OCR)
#                     image_list = page_fitz.get_images(full=True)
#                     for img_idx, img_info in enumerate(image_list):
#                         xref = img_info[0]
#                         rects = page_fitz.get_image_rects(xref)
                        
#                         base_image = doc_fitz.extract_image(xref)
#                         image_bytes = base_image["image"]
#                         image_ext = base_image["ext"]
#                         image_filename = f"page_{page_num}_img_{img_idx + 1}.{image_ext}"
#                         image_path = folders["images"] / image_filename
                        
#                         self._save_image(image_bytes, image_path)

#                         for rect in rects:
#                             raw_page_elements.append({
#                                 "type": "image",
#                                 "image_index": img_idx + 1,
#                                 "xref": xref,
#                                 "bbox": self._bbox([rect.x0, rect.y0, rect.x1, rect.y1]),
#                                 "image_path": f"/storage/processed/{document_id}/images/{image_filename}",
#                                 "width": round(rect.width, 2),
#                                 "height": round(rect.height, 2)
#                             })

#                     # 3. TEXT & HEADINGS
#                     blocks = page_fitz.get_text("dict").get("blocks", [])
                    
#                     if not blocks:
#                         page_text = self._ocr_full_page(page_fitz)
                        
#                         if page_text:
#                             raw_page_elements.append({
#                                 "type": "paragraph",
#                                 "text": page_text,
#                                 "font_size": 12.0,
#                                 "is_bold": False,
#                                 "bbox": self._bbox([0, 0, page_fitz.rect.width, page_fitz.rect.height])
#                             })
#                         else:
#                             # 🚨 ENTERPRISE SAFEGUARD: Never discard a page. Insert a placeholder.
#                             logger.warning(f"No extractable text found on page {page_num}. Marking as scanned_page for future processing.")
#                             raw_page_elements.append({
#                                 "type": "scanned_page",
#                                 "text": "",
#                                 "font_size": 0,
#                                 "is_bold": False,
#                                 "bbox": self._bbox([0, 0, page_fitz.rect.width, page_fitz.rect.height]),
#                                 "requires_ocr": True
#                             })
#                     else:
#                         for block in blocks:
#                             if block.get("type") != 0: 
#                                 continue
                            
#                             block_bbox = self._bbox(block["bbox"])
#                             if self._inside_table(block_bbox, table_bboxes):
#                                 continue

#                             block_text = ""
#                             max_font_size = 0.0
#                             is_bold = False

#                             for line in block.get("lines", []):
#                                 for span in line.get("spans", []):
#                                     block_text += span.get("text", "")
#                                     size = span.get("size", 0)
#                                     if size > max_font_size: max_font_size = size
#                                     flags = span.get("flags", 0)
#                                     if (flags & 2) or "bold" in span.get("font", "").lower():
#                                         is_bold = True
#                                 block_text += " "

#                             block_text = block_text.strip()
#                             if not block_text:
#                                 continue

#                             # Pre-classification of element type using robust logic
#                             element_type = "heading" if self._heading_level(max_font_size, is_bold) > 0 else "paragraph"
#                             if re.match(r"^(fig\.?|figure|table|chart)\s*\d+", block_text, re.IGNORECASE):
#                                 element_type = "caption"

#                             raw_page_elements.append({
#                                 "type": "element_type",
#                                 "text": block_text,
#                                 "font_size": round(max_font_size, 1),
#                                 "is_bold": is_bold,
#                                 "bbox": block_bbox
#                             })

#                     # 4. PAGE-LEVEL SORTING & ID ASSIGNMENT
#                     sorted_page_elements = self._sort_reading_order(raw_page_elements)
                    
#                     for el in sorted_page_elements:
#                         el_type = el["type"]
#                         el["page_number"] = page_num
#                         el["element_id"] = f"{document_id}_p{page_num}_{el_type}_{global_sequence_index}"
#                         el["reading_sequence"] = global_sequence_index
#                         global_elements.append(el)
#                         global_sequence_index += 1

#             doc_fitz.close()

#             # ---------------------------------------------------------
#             # 5. CROSS-DOCUMENT GRAPH & POINTER RESOLUTION
#             # ---------------------------------------------------------
#             document_graph = self._build_document_graph_and_pointers(global_elements)

#             # Re-group augmented elements back into pages for backward compatibility
#             # Ensure every single page is explicitly represented to preserve pagination numbering.
#             for page_num in range(1, total_pages + 1):
#                 page_elems = [e for e in global_elements if e.get("page_number") == page_num]
                
#                 page_headings = [e["text"] for e in page_elems if e.get("type") == "heading"]
#                 full_text_str = "\n\n".join([e.get("text", "") for e in page_elems if "text" in e])

#                 pages_data.append({
#                     "page_number": page_num,
#                     "headings": page_headings,
#                     "elements_count": len(page_elems),
#                     "elements": page_elems,
#                     "full_text": full_text_str
#                 })

#             # ---------------------------------------------------------
#             # 6. ASSEMBLE FINAL JSON
#             # ---------------------------------------------------------
#             document_tree = {
#                 "document_id": document_id,
#                 "total_pages": total_pages,
#                 "has_native_toc": len(table_of_contents) > 0,
#                 "table_of_contents": table_of_contents,
#                 "document_graph": document_graph,
#                 "pages": pages_data
#             }

#             tree_path = folders["root"] / "document_tree.json"
#             with open(tree_path, "w", encoding="utf-8") as f:
#                 json.dump(document_tree, f, indent=4, ensure_ascii=False)

#             logger.info(f"Successfully processed highly relational document structure for {document_id}")
#             return document_tree

#         except Exception as e:
#             logger.error(f"Error building relational document tree for {document_id}: {str(e)}", exc_info=True)
#             raise ProcessingError(f"Failed to extract document structure: {str(e)}")





# WORKING---------------

# import io
# import json
# import re
# import math
# import hashlib
# import statistics
# import copy
# import time
# import shutil
# from collections import Counter
# from pathlib import Path
# from typing import Any, Dict, List, Tuple

# import pymupdf as fitz
# import pdfplumber
# from PIL import Image

# try:
#     import pytesseract
#     from pytesseract import Output
#     PYTESSERACT_AVAILABLE = True
# except ImportError:
#     PYTESSERACT_AVAILABLE = False

# from app.core.config import settings
# from app.core.logger import logger


# class StructureService:
#     def __init__(self):
#         self.raw_dir = settings.STORAGE_RAW_DIR
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR
#         self.tesseract_config = "--oem 3 --psm 3"
#         self.schema_version = "1.6"
#         self.extraction_version = "structure-v10-validation"
        
#         # Deterministic OCR Backend Check
#         self.tesseract_exe_found = shutil.which("tesseract") is not None
#         self.ocr_available = PYTESSERACT_AVAILABLE and self.tesseract_exe_found
        
#         if not self.ocr_available:
#             logger.warning("OCR backend: Tesseract executable unavailable. OCR fallback disabled.")
#         else:
#             logger.info("OCR backend: Tesseract available and verified in PATH.")

#     ###########################################################################
#     # 1. IO, GEOMETRY, & HASHING
#     ###########################################################################

#     def _locate_pdf(self, document_id: str) -> Path:
#         for p in [self.raw_dir / document_id / "original.pdf", self.raw_dir / f"{document_id}.pdf"]:
#             if p.exists(): return p
#         raise FileNotFoundError(f"PDF document not found for ID: {document_id}")

#     def _setup_directories(self, document_id: str) -> Dict[str, Path]:
#         root = self.processed_dir / document_id
#         folders = {"root": root, "assets": root / "assets"}
#         for f in folders.values(): f.mkdir(parents=True, exist_ok=True)
#         return folders

#     def _hash_content(self, data: bytes) -> str:
#         return hashlib.sha256(data).hexdigest()

#     def _generate_provenance_id(self, doc_hash: str, page: int, bbox: List[float], el_type: str, content: str, index: int) -> str:
#         content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()[:12] if content else "empty"
#         bbox_str = f"{round(bbox[0],1)}_{round(bbox[1],1)}_{round(bbox[2],1)}_{round(bbox[3],1)}" if bbox else "none"
#         sig = f"{doc_hash}|p{page}|type:{el_type}|box:{bbox_str}|c:{content_hash}|idx:{index}"
#         return hashlib.sha256(sig.encode('utf-8')).hexdigest()

#     def _bbox(self, bbox) -> List[float]:
#         if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
#             return None
#         try:
#             return [round(float(x), 2) for x in bbox]
#         except (ValueError, TypeError):
#             return None

#     def _calculate_overlap_ratio(self, box1: List[float], box2: List[float]) -> float:
#         if not box1 or not box2: return 0.0
#         dx = min(box1[2], box2[2]) - max(box1[0], box2[0])
#         dy = min(box1[3], box2[3]) - max(box1[1], box2[1])
#         if dx > 0 and dy > 0:
#             overlap_area = dx * dy
#             area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
#             return overlap_area / area1 if area1 > 0 else 0.0
#         return 0.0

#     def _token_similarity(self, text1: str, text2: str) -> float:
#         t1 = set(re.findall(r'\w+', text1.lower()))
#         t2 = set(re.findall(r'\w+', text2.lower()))
#         if not t1 or not t2: return 0.0
#         return len(t1 & t2) / len(t1 | t2)

#     ###########################################################################
#     # 2. ISOLATED COMPONENT: SAFE TABLE EXTRACTION
#     ###########################################################################

#     def _extract_tables_safely(self, page_plumber, page_num: int, page_h: float) -> Tuple[List[Dict], List[Dict]]:
#         """Text grid is the source of truth. Geometry is mapped ONLY if perfectly aligned."""
#         tables_data, warnings = [], []
        
#         try:
#             for table_obj in page_plumber.find_tables():
#                 try:
#                     raw_grid = table_obj.extract()
#                 except Exception as e:
#                     warnings.append({"page_number": page_num, "component": "table", "warning": f"Grid text extraction failed: {str(e)}"})
#                     continue

#                 if not isinstance(raw_grid, list) or not raw_grid:
#                     warnings.append({"page_number": page_num, "component": "table", "warning": "Extracted grid is empty or malformed."})
#                     continue

#                 bbox = self._bbox(table_obj.bbox) if hasattr(table_obj, "bbox") else None
#                 cells = []
#                 geom_status = "unavailable"
                
#                 # Independent Geometry Attempt
#                 valid_cells_geom = getattr(table_obj, "cells", [])
#                 total_grid_cells = sum(len(row) for row in raw_grid if isinstance(row, (list, tuple)))
                
#                 # Only map 1:1 if the flat pdfplumber cell array length matches the logical 2D grid cell count
#                 can_map_1_to_1 = isinstance(valid_cells_geom, list) and len(valid_cells_geom) == total_grid_cells
#                 if can_map_1_to_1:
#                     geom_status = "available"
#                 else:
#                     warnings.append({"page_number": page_num, "component": "table_geometry", "warning": "Geometry length mismatch. Bboxes set to null to protect text integrity."})

#                 geom_idx = 0
#                 for r_idx, row in enumerate(raw_grid):
#                     if not isinstance(row, (list, tuple)): 
#                         row = [str(row)] 
                        
#                     for c_idx, cell_text in enumerate(row):
#                         cell_bbox, bbox_source = None, "unavailable"
                        
#                         if can_map_1_to_1:
#                             try:
#                                 c_geom = valid_cells_geom[geom_idx]
#                                 parsed_bbox = self._bbox(c_geom)
#                                 if parsed_bbox:
#                                     cell_bbox = parsed_bbox
#                                     bbox_source = "pdfplumber"
#                             except Exception:
#                                 geom_status = "partial"
#                             geom_idx += 1

#                         cells.append({
#                             "row_idx": r_idx, "col_idx": c_idx,
#                             "row_span": 1, "col_span": 1, # Kept as baseline until merged span logic is proven
#                             "bbox": cell_bbox, "bbox_source": bbox_source,
#                             "text": str(cell_text).strip() if cell_text is not None else "",
#                             "is_header": r_idx == 0, 
#                             "is_merged": False
#                         })
                
#                 tables_data.append({
#                     "type": "table", "bbox": bbox, "page_number": page_num,
#                     "extraction_method": "native_pdf", "cells": cells, "_page_height": page_h,
#                     "col_count": len(raw_grid[0]) if isinstance(raw_grid[0], (list, tuple)) else 0,
#                     "geometry_status": geom_status,
#                     "text_status": "available"
#                 })
#         except Exception as e:
#             warnings.append({"page_number": page_num, "component": "table_fatal", "error": f"Table block skipped: {str(e)}"})
            
#         return tables_data, warnings

#     ###########################################################################
#     # 3. PAGE STRATEGY & ISOLATED OCR
#     ###########################################################################

#     def _evaluate_page_strategy(self, page: fitz.Page, blocks: List[Dict]) -> str:
#         if not blocks: return "OCR_ONLY"
#         text_chars = sum(len(s.get("text", "")) for b in blocks for l in b.get("lines", []) for s in l.get("spans", []) if b.get("type") == 0)
#         page_area = page.rect.width * page.rect.height
#         printable_ratio = text_chars / page_area if page_area else 0
#         img_area = sum((r.x1-r.x0)*(r.y1-r.y0) for img in page.get_images() for r in page.get_image_rects(img[0]))
#         img_coverage = img_area / page_area if page_area else 0

#         if text_chars < 50 and img_coverage > 0.10: return "OCR_ONLY"
#         if printable_ratio < 0.005 or img_coverage > 0.30: return "HYBRID"
#         return "NATIVE_ONLY"

#     def _ocr_extract_safely(self, page: fitz.Page, native_bboxes: List[List[float]] = None, native_texts: List[str] = None) -> Tuple[List[Dict], str]:
#         if not self.ocr_available:
#             return [], "unavailable"
            
#         try:
#             pix = page.get_pixmap(dpi=300)
#             img = Image.open(io.BytesIO(pix.tobytes("png")))
#             data = pytesseract.image_to_data(img, config=self.tesseract_config, output_type=Output.DICT)
            
#             blocks, scale = {}, 72.0 / 300.0
#             for i in range(len(data['text'])):
#                 word = data['text'][i].strip()
#                 try: conf = float(data['conf'][i])
#                 except (ValueError, TypeError): continue
                
#                 if conf > 30 and word:
#                     b_id = f"{data['block_num'][i]}_{data['par_num'][i]}_{data['line_num'][i]}"
#                     if b_id not in blocks:
#                         blocks[b_id] = {"text": [], "conf": [], "x0": data['left'][i], "y0": data['top'][i], "x1": data['left'][i]+data['width'][i], "y1": data['top'][i]+data['height'][i]}
#                     else:
#                         b = blocks[b_id]
#                         b["x0"], b["y0"] = min(b["x0"], data['left'][i]), min(b["y0"], data['top'][i])
#                         b["x1"], b["y1"] = max(b["x1"], data['left'][i]+data['width'][i]), max(b["y1"], data['top'][i]+data['height'][i])
#                     blocks[b_id]["text"].append(word)
#                     blocks[b_id]["conf"].append(conf)

#             ocr_elements = []
#             for b in blocks.values():
#                 bbox = self._bbox([b["x0"]*scale, b["y0"]*scale, b["x1"]*scale, b["y1"]*scale])
#                 text = " ".join(b["text"])
                
#                 is_duplicate = False
#                 if native_bboxes and native_texts:
#                     for n_idx, n_box in enumerate(native_bboxes):
#                         if self._calculate_overlap_ratio(bbox, n_box) > 0.5:
#                             if self._token_similarity(text, native_texts[n_idx]) > 0.6:
#                                 is_duplicate = True
#                                 break
                
#                 if not is_duplicate:
#                     ocr_elements.append({
#                         "type": "raw_text", "text": text,
#                         "extraction_method": "ocr", "extraction_confidence": round(statistics.mean(b["conf"])/100.0, 2),
#                         "ocr_status": "success", # Element-level provenance
#                         "bbox": bbox, "font_size": None, 
#                         "estimated_font_size": round(bbox[3] - bbox[1], 1) if bbox else 12.0, 
#                         "font_source": "ocr_estimate"
#                     })
#             return ocr_elements, "success"
#         except Exception as e:
#             return [], f"failed: {str(e)}"

#     ###########################################################################
#     # 4. SPATIAL LAYOUT & READING ORDER
#     ###########################################################################

#     def _sort_reading_order(self, elements: List[Dict], page_width: float) -> List[Dict]:
#         if not elements: return []
#         full_width, others = [], []
#         for el in elements:
#             if el.get("bbox") and (el["bbox"][2] - el["bbox"][0]) > page_width * 0.70: 
#                 full_width.append(el)
#             else: 
#                 others.append(el)
            
#         full_width.sort(key=lambda e: e["bbox"][1] if e.get("bbox") else 0)
#         final_order, current_y = [], 0.0
        
#         for fw in full_width:
#             band_elements = [e for e in others if e.get("bbox") and e["bbox"][1] >= current_y and e["bbox"][3] <= fw["bbox"][1] + 15]
#             final_order.extend(self._sort_band_columns(band_elements))
#             final_order.append(fw)
#             current_y = fw["bbox"][3]
            
#         remaining = [e for e in others if e.get("bbox") and e["bbox"][1] >= current_y]
#         final_order.extend(self._sort_band_columns(remaining))
#         final_order.extend([e for e in others if not e.get("bbox")])
#         return final_order

#     def _sort_band_columns(self, band_elements: List[Dict]) -> List[Dict]:
#         if not band_elements: return []
#         left_edges = sorted([e["bbox"][0] for e in band_elements if e.get("bbox")])
#         if not left_edges: return band_elements
        
#         column_bounds = []
#         for x0 in left_edges:
#             if not column_bounds or (x0 - column_bounds[-1]["x0"]) > 60:
#                 column_bounds.append({"x0": x0, "elements": []})

#         for el in band_elements:
#             if not el.get("bbox"): continue
#             best_col, min_dist = column_bounds[0], float('inf')
#             cx = (el["bbox"][0] + el["bbox"][2]) / 2
#             for col in column_bounds:
#                 dist = abs(cx - col["x0"]) 
#                 if dist < min_dist: min_dist, best_col = dist, col
#             best_col["elements"].append(el)

#         band_order = []
#         for col in column_bounds:
#             band_order.extend(sorted(col["elements"], key=lambda e: e["bbox"][1]))
#         return band_order

#     ###########################################################################
#     # 5. MASTER EXTRACTION PIPELINE
#     ###########################################################################

#     async def build_structural_tree(self, document_id: str) -> Dict[str, Any]:
#         pdf_path = self._locate_pdf(document_id)
#         folders = self._setup_directories(document_id)
#         pdf_hash = self._hash_content(pdf_path.read_bytes())
        
#         raw_elements, image_assets = [], {}
#         page_metrics, page_warnings, page_failures = [], [], []
#         toc_entries = []

#         stats = {
#             "total_pages": 0, "pages_processed": 0, "pages_with_native_text": 0,
#             "pages_with_ocr": 0, "pages_ocr_unavailable": 0, "pages_ocr_failed": 0, 
#             "pages_with_warnings": 0, "pages_failed": 0, "tables_extracted": 0, 
#             "unique_image_assets_extracted": 0, "image_occurrences_extracted": 0
#         }

#         with fitz.open(str(pdf_path)) as doc_fitz, pdfplumber.open(str(pdf_path)) as doc_plumber:
#             stats["total_pages"] = len(doc_fitz)
#             table_of_contents = [{"level": i[0], "title": i[1].strip(), "page_number": i[2]} for i in doc_fitz.get_toc()]
#             toc_entries = [t["title"].lower() for t in table_of_contents if t.get("title")]
            
#             for page_idx in range(stats["total_pages"]):
#                 page_num = page_idx + 1
#                 t_start = time.time()
#                 page_has_warning = False
                
#                 try:
#                     page_fitz = doc_fitz[page_idx]
#                     page_plumber = doc_plumber.pages[page_idx]
#                     page_h, page_w = page_fitz.rect.height, page_fitz.rect.width
#                 except Exception as e:
#                     page_failures.append({"page_number": page_num, "error": f"Fatal page load failure: {str(e)}"})
#                     stats["pages_failed"] += 1
#                     continue
                
#                 page_raw, native_bboxes, native_texts = [], [], []

#                 # 1. STRATEGY EVALUATION (Fault Isolated)
#                 try:
#                     blocks = page_fitz.get_text("dict").get("blocks", [])
#                     strategy = self._evaluate_page_strategy(page_fitz, blocks)
#                 except Exception as e:
#                     page_warnings.append({"page_number": page_num, "component": "strategy", "warning": f"Eval failed: {str(e)}"})
#                     strategy, blocks = "NATIVE_ONLY", []
#                     page_has_warning = True

#                 # 2. TABLES (Fault Isolated)
#                 tables_data, tbl_warnings = self._extract_tables_safely(page_plumber, page_num, page_h)
#                 if tbl_warnings: 
#                     page_warnings.extend(tbl_warnings)
#                     page_has_warning = True
#                 page_raw.extend(tables_data)
#                 stats["tables_extracted"] += len(tables_data)

#                 # 3. IMAGES (Fault Isolated)
#                 try:
#                     for img_info in page_fitz.get_images(full=True):
#                         xref = img_info[0]
#                         base_img = doc_fitz.extract_image(xref)
#                         img_hash = self._hash_content(base_img["image"])[:16]
#                         asset_id = f"asset_{document_id}_{img_hash}"
                        
#                         if asset_id not in image_assets:
#                             img_path = f"{asset_id}.{base_img['ext']}"
#                             with open(folders["assets"] / img_path, "wb") as f: f.write(base_img["image"])
#                             image_assets[asset_id] = {
#                                 "asset_id": asset_id, "xref_original": xref, "hash": img_hash,
#                                 "width": base_img["width"], "height": base_img["height"], 
#                                 "ext": base_img["ext"], "path": f"assets/{img_path}", "occurrence_count": 0
#                             }
#                             stats["unique_image_assets_extracted"] += 1
                        
#                         image_assets[asset_id]["occurrence_count"] += 1
#                         stats["image_occurrences_extracted"] += 1
#                         for rect in page_fitz.get_image_rects(xref):
#                             page_raw.append({
#                                 "type": "image_occurrence", "asset_id": asset_id,
#                                 "bbox": self._bbox([rect.x0, rect.y0, rect.x1, rect.y1]),
#                                 "page_number": page_num, "extraction_method": "native_pdf", "_page_height": page_h
#                             })
#                 except Exception as e:
#                     page_warnings.append({"page_number": page_num, "component": "image", "warning": str(e)})
#                     page_has_warning = True

#                 # 4. NATIVE TEXT (Fault Isolated)
#                 native_extracted = False
#                 if strategy in ["NATIVE_ONLY", "HYBRID"]:
#                     try:
#                         for block in blocks:
#                             if block.get("type") != 0: continue
#                             bbox = self._bbox(block["bbox"])
#                             text, max_font, is_bold, font_name = "", 0.0, False, ""
#                             for l in block.get("lines", []):
#                                 for s in l.get("spans", []):
#                                     text += s.get("text", "")
#                                     max_font = max(max_font, s.get("size", 0))
#                                     font_name = s.get("font", "")
#                                     if (s.get("flags", 0) & 2) or "bold" in font_name.lower(): is_bold = True
#                                 text += " "
                            
#                             text = text.strip()
#                             if text:
#                                 native_bboxes.append(bbox)
#                                 native_texts.append(text)
#                                 native_extracted = True
#                                 page_raw.append({
#                                     "type": "raw_text", "text": text, "font_size": round(max_font, 1),
#                                     "font_family": font_name, "font_source": "native_pdf",
#                                     "is_bold": is_bold, "bbox": bbox, "page_number": page_num,
#                                     "extraction_method": "native_pdf", "_page_height": page_h
#                                 })
#                         if native_extracted: stats["pages_with_native_text"] += 1
#                     except Exception as e:
#                         page_warnings.append({"page_number": page_num, "component": "native_text", "warning": str(e)})
#                         page_has_warning = True

#                 # 5. OCR (Strictly Isolated & Explicit State)
#                 if strategy in ["OCR_ONLY", "HYBRID"]:
#                     args = (page_fitz,) if strategy == "OCR_ONLY" else (page_fitz, native_bboxes, native_texts)
#                     ocr_blocks, ocr_status = self._ocr_extract_safely(*args)
                    
#                     if ocr_status == "success":
#                         for b in ocr_blocks:
#                             b["page_number"] = page_num
#                             b["_page_height"] = page_h
#                         page_raw.extend(ocr_blocks)
#                         stats["pages_with_ocr"] += 1
#                     else:
#                         page_warnings.append({"page_number": page_num, "component": "ocr", "warning": f"Status: {ocr_status}"})
#                         page_has_warning = True
                        
#                         if ocr_status == "unavailable": stats["pages_ocr_unavailable"] += 1
#                         elif ocr_status.startswith("failed"): stats["pages_ocr_failed"] += 1
                        
#                         if strategy == "OCR_ONLY":
#                             page_raw.append({
#                                 "type": "scanned_page", "bbox": [0.0, 0.0, page_w, page_h],
#                                 "page_number": page_num, "text": "", "ocr_status": ocr_status,
#                                 "extraction_method": "unavailable", "_page_height": page_h
#                             })

#                 try:
#                     sorted_page = self._sort_reading_order(page_raw, page_w)
#                     raw_elements.extend(sorted_page)
#                 except Exception as e:
#                     page_warnings.append({"page_number": page_num, "component": "layout_sort", "warning": str(e)})
#                     raw_elements.extend(page_raw) 
#                     page_has_warning = True

#                 if page_has_warning: stats["pages_with_warnings"] += 1
#                 stats["pages_processed"] += 1
#                 page_metrics.append({"page": page_num, "strategy": strategy, "duration_sec": round(time.time() - t_start, 2)})

#         # --- PRE-PERSISTENCE: MARK FURNITURE & ASSIGN IDS ---
#         margins = []
#         for el in raw_elements:
#             if el.get("type") == "raw_text" and el.get("bbox"):
#                 y0, y1 = el["bbox"][1], el["bbox"][3]
#                 page_h = el.get("_page_height", 800)
#                 if y1 < page_h * 0.08 or y0 > page_h * 0.92:
#                     margins.append(re.sub(r'\d+', '#', el["text"].strip().lower()))
                    
#         freq, threshold = Counter(margins), max(3, int(stats["total_pages"] * 0.05))
#         for el in raw_elements:
#             el["is_furniture"] = False
#             if el.get("type") == "raw_text" and el.get("bbox"):
#                 y0, y1 = el["bbox"][1], el["bbox"][3]
#                 if y1 < el.get("_page_height", 800) * 0.08 or y0 > el.get("_page_height", 800) * 0.92:
#                     if freq[re.sub(r'\d+', '#', el["text"].strip().lower())] > threshold:
#                         el["is_furniture"] = True

#         doc_seq = 1
#         current_page, page_seq = -1, 1
#         for el in raw_elements:
#             if el["page_number"] != current_page:
#                 current_page, page_seq = el["page_number"], 1
#             el_type_short = el['type'].split('_')[0]
#             el["element_id"] = f"{document_id}_p{current_page}_s{page_seq}_{el_type_short}"
#             el["provenance_id"] = self._generate_provenance_id(pdf_hash, current_page, el.get("bbox"), el["type"], el.get("text", ""), doc_seq)
#             el["document_sequence"] = doc_seq
#             el["page_sequence"] = page_seq
#             doc_seq += 1
#             page_seq += 1

#         with open(folders["root"] / "raw_elements.jsonl", "w") as f:
#             for el in raw_elements: f.write(json.dumps({k:v for k,v in el.items() if not k.startswith("_")}) + "\n")

#         # --- PHASE 2: NORMALIZATION (Deep Copy) ---
#         normalized_elements = [copy.deepcopy(el) for el in raw_elements if not el.get("is_furniture")]
#         base_fonts = [e.get("font_size") for e in normalized_elements if e.get("type") == "raw_text" and e.get("font_size")]
#         median_font = statistics.median(base_fonts) if base_fonts else 12.0
        
#         for el in normalized_elements:
#             if el["type"] == "raw_text":
#                 text = el["text"]
#                 fs = el.get("font_size") or el.get("estimated_font_size", 12.0)
#                 is_bold = el.get("is_bold", False)
#                 has_num = bool(re.match(r'^((Chapter|Section)\s+[IVX\d]+|\d+(\.\d+)+)\b', text, re.IGNORECASE))
                
#                 h_level, h_conf = 0, 1.0
#                 if 0 < len(text.split()) <= 15:
#                     toc_match = any(self._token_similarity(text.lower(), toc) > 0.8 for toc in toc_entries)
#                     if toc_match and (fs > median_font + 1.0 or is_bold or has_num):
#                         h_level, h_conf = 2, 0.95 
#                         if fs > median_font + 2.0: h_level = 1
#                     elif fs > median_font + 3.0:
#                         h_level, h_conf = 1, 0.90
#                     elif (fs > median_font + 1.0) or (is_bold and has_num):
#                         h_level, h_conf = 2, 0.85
                        
#                 if h_level > 0:
#                     el["type"] = "heading"
#                     el["heading_level"] = h_level
#                     el["classification_confidence"] = h_conf
#                 elif re.match(r"^(fig\.?|figure|table|chart)\s*\d+", text, re.IGNORECASE):
#                     el["type"] = "caption"
#                     el["classification_confidence"] = 0.90
#                 else:
#                     el["type"] = "paragraph"

#         # --- PHASE 3: GRAPH EDGES ---
#         graph_nodes, active_path, table_group_counter = [], [], 1
#         page_targets = {}
#         for el in normalized_elements:
#             if el["type"] in ["table", "image_occurrence"]:
#                 page_targets.setdefault(el["page_number"], []).append(el)

#         for i, el in enumerate(normalized_elements):
#             el["previous_element_id"] = normalized_elements[i-1]["element_id"] if i > 0 else None
#             el["next_element_id"] = normalized_elements[i+1]["element_id"] if i < len(normalized_elements)-1 else None
#             el["parent_section_id"], el["caption_element_id"], el["target_element_id"] = None, None, None
#             el["continues_from_element_id"], el["continues_to_element_id"] = None, None

#             if el["type"] == "heading":
#                 level = el["heading_level"]
#                 while active_path and active_path[-1]["level"] >= level: active_path.pop()
#                 active_path.append({"element_id": el["element_id"], "level": level, "text": el["text"]})
            
#             if active_path:
#                 el["parent_section_id"] = active_path[-1]["element_id"]
#                 el["context"] = {
#                     "source": "heading_inheritance",
#                     "path": [dict(p) for p in active_path],
#                     "path_element_ids": [p["element_id"] for p in active_path]
#                 }

#             if el["type"] == "table" and i > 0:
#                 prev = normalized_elements[i-1]
#                 if prev["type"] == "table" and el["page_number"] - prev["page_number"] <= 1:
#                     if prev.get("col_count") == el.get("col_count") and prev.get("bbox") and el.get("bbox"):
#                         if abs(prev["bbox"][0] - el["bbox"][0]) < 20 and abs(prev["bbox"][2] - el["bbox"][2]) < 20:
#                             grp = prev.get("table_group_id", f"tblgrp_{document_id}_{table_group_counter}")
#                             table_group_counter += 1
#                             prev["table_group_id"], el["table_group_id"] = grp, grp
#                             prev["continues_to_element_id"] = el["element_id"]
#                             el["continues_from_element_id"] = prev["element_id"]

#             if el["type"] == "caption" and el.get("bbox"):
#                 best_dist, best_target = float('inf'), None
#                 for target in page_targets.get(el["page_number"], []):
#                     if not target.get("bbox"): continue
#                     cap_center = (el["bbox"][0] + el["bbox"][2]) / 2
#                     tar_center = (target["bbox"][0] + target["bbox"][2]) / 2
#                     if abs(cap_center - tar_center) < 150: 
#                         dy = min(abs(el["bbox"][1] - target["bbox"][3]), abs(target["bbox"][1] - el["bbox"][3]))
#                         if dy < best_dist and dy < 150: 
#                             best_dist, best_target = dy, target
#                 if best_target:
#                     el["target_element_id"] = best_target["element_id"]
#                     best_target["caption_element_id"] = el["element_id"]

#             graph_nodes.append({
#                 "element_id": el["element_id"], "provenance_id": el["provenance_id"],
#                 "parent_section_id": el.get("parent_section_id"), "previous_element_id": el.get("previous_element_id"),
#                 "next_element_id": el.get("next_element_id"), "caption_element_id": el.get("caption_element_id"),
#                 "target_element_id": el.get("target_element_id"), "continues_from_element_id": el.get("continues_from_element_id"),
#                 "continues_to_element_id": el.get("continues_to_element_id")
#             })

#         # --- PHASE 4: PERSISTENCE & COMPLIANT API RETURN ---
#         manifest = {
#             "document_id": document_id, "schema_version": self.schema_version,
#             "extraction_version": self.extraction_version, "source_pdf_hash": pdf_hash,
#             "ocr_health": {
#                 "provider": "tesseract", "python_package_available": PYTESSERACT_AVAILABLE,
#                 "executable_available": self.tesseract_exe_found, "available": self.ocr_available,
#                 "reason": "tesseract_executable_not_found" if not self.tesseract_exe_found else "ok"
#             },
#             "extraction_summary": stats,
#             "page_failures": page_failures, "page_warnings": page_warnings,
#             "page_metrics": page_metrics
#         }

#         with open(folders["root"] / "manifest.json", "w") as f: json.dump(manifest, f, indent=2)
#         with open(folders["root"] / "assets_manifest.json", "w") as f: json.dump(list(image_assets.values()), f, indent=2)
#         with open(folders["root"] / "normalized_elements.jsonl", "w") as f:
#             for el in normalized_elements: f.write(json.dumps({k:v for k,v in el.items() if not k.startswith("_")}) + "\n")
#         with open(folders["root"] / "structural_graph.json", "w") as f: json.dump(graph_nodes, f, indent=2)

#         summary = {
#             "success": True, "message": "Structure extraction complete.",
#             "data": {
#                 "manifest": manifest,
#                 "data_locations": {
#                     "raw": f"/storage/processed/{document_id}/raw_elements.jsonl",
#                     "normalized": f"/storage/processed/{document_id}/normalized_elements.jsonl",
#                     "graph": f"/storage/processed/{document_id}/structural_graph.json",
#                     "assets": f"/storage/processed/{document_id}/assets_manifest.json"
#                 }
#             }
#         }
#         logger.info(f"Structure extraction and provenance established for {document_id}")
#         return summary






# import io
# import json
# import re
# import math
# import hashlib
# import statistics
# import copy
# import time
# import shutil
# from collections import Counter
# from pathlib import Path
# from typing import Any, Dict, List, Tuple

# import pymupdf as fitz
# import pdfplumber
# from PIL import Image

# try:
#     import pytesseract
#     from pytesseract import Output
#     PYTESSERACT_AVAILABLE = True
# except ImportError:
#     PYTESSERACT_AVAILABLE = False

# from app.core.config import settings
# from app.core.logger import logger


# class StructureService:
#     def __init__(self):
#         self.raw_dir = settings.STORAGE_RAW_DIR
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR
#         self.tesseract_config = "--oem 3 --psm 3"
#         self.schema_version = "1.8"
#         self.extraction_version = "structure-v12-demo-ready"
        
#         # Deterministic OCR Backend Check
#         self.tesseract_exe_found = shutil.which("tesseract") is not None
#         self.ocr_available = PYTESSERACT_AVAILABLE and self.tesseract_exe_found
        
#         if not self.ocr_available:
#             logger.warning("OCR backend: Tesseract executable unavailable. OCR fallback disabled.")
#         else:
#             logger.info("OCR backend: Tesseract available and verified in PATH.")

#     ###########################################################################
#     # 1. IO, GEOMETRY, & HASHING
#     ###########################################################################

#     def _locate_pdf(self, document_id: str) -> Path:
#         for p in [self.raw_dir / document_id / "original.pdf", self.raw_dir / f"{document_id}.pdf"]:
#             if p.exists(): return p
#         raise FileNotFoundError(f"PDF document not found for ID: {document_id}")

#     def _setup_directories(self, document_id: str) -> Dict[str, Path]:
#         root = self.processed_dir / document_id
#         folders = {"root": root, "assets": root / "assets"}
#         for f in folders.values(): f.mkdir(parents=True, exist_ok=True)
#         return folders

#     def _hash_content(self, data: bytes) -> str:
#         return hashlib.sha256(data).hexdigest()

#     def _generate_provenance_id(self, doc_hash: str, page: int, bbox: List[float], el_type: str, content: str, index: int) -> str:
#         content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()[:12] if content else "empty"
#         bbox_str = f"{round(bbox[0],1)}_{round(bbox[1],1)}_{round(bbox[2],1)}_{round(bbox[3],1)}" if bbox else "none"
#         sig = f"{doc_hash}|p{page}|type:{el_type}|box:{bbox_str}|c:{content_hash}|idx:{index}"
#         return hashlib.sha256(sig.encode('utf-8')).hexdigest()

#     def _bbox(self, bbox) -> List[float]:
#         if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
#             return None
#         try:
#             return [round(float(x), 2) for x in bbox]
#         except (ValueError, TypeError):
#             return None

#     def _calculate_overlap_ratio(self, box1: List[float], box2: List[float]) -> float:
#         if not box1 or not box2: return 0.0
#         dx = min(box1[2], box2[2]) - max(box1[0], box2[0])
#         dy = min(box1[3], box2[3]) - max(box1[1], box2[1])
#         if dx > 0 and dy > 0:
#             overlap_area = dx * dy
#             area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
#             return overlap_area / area1 if area1 > 0 else 0.0
#         return 0.0

#     def _token_similarity(self, text1: str, text2: str) -> float:
#         t1 = set(re.findall(r'\w+', text1.lower()))
#         t2 = set(re.findall(r'\w+', text2.lower()))
#         if not t1 or not t2: return 0.0
#         return len(t1 & t2) / len(t1 | t2)

#     ###########################################################################
#     # 2. ISOLATED COMPONENT: SAFE TABLE EXTRACTION
#     ###########################################################################

#     def _extract_tables_safely(self, page_plumber, page_num: int, page_h: float) -> Tuple[List[Dict], List[Dict]]:
#         """Text grid is the source of truth. Geometry is mapped ONLY if perfectly aligned."""
#         tables_data, warnings = [], []
        
#         try:
#             for table_obj in page_plumber.find_tables():
#                 try:
#                     raw_grid = table_obj.extract()
#                 except Exception as e:
#                     warnings.append({"page_number": page_num, "component": "table", "warning": f"Grid text extraction failed: {str(e)}"})
#                     continue

#                 if not isinstance(raw_grid, list) or not raw_grid:
#                     continue # Silently skip empty grids

#                 bbox = self._bbox(table_obj.bbox) if hasattr(table_obj, "bbox") else None
#                 cells = []
#                 geom_status = "unavailable"
                
#                 # Independent Geometry Attempt
#                 valid_cells_geom = getattr(table_obj, "cells", [])
#                 total_grid_cells = sum(len(row) for row in raw_grid if isinstance(row, (list, tuple)))
                
#                 can_map_1_to_1 = isinstance(valid_cells_geom, list) and len(valid_cells_geom) == total_grid_cells
#                 if can_map_1_to_1:
#                     geom_status = "available"

#                 geom_idx = 0
#                 for r_idx, row in enumerate(raw_grid):
#                     if not isinstance(row, (list, tuple)): 
#                         row = [str(row)] 
                        
#                     for c_idx, cell_text in enumerate(row):
#                         cell_bbox, bbox_source = None, "unavailable"
                        
#                         if can_map_1_to_1:
#                             try:
#                                 c_geom = valid_cells_geom[geom_idx]
#                                 parsed_bbox = self._bbox(c_geom)
#                                 if parsed_bbox:
#                                     cell_bbox = parsed_bbox
#                                     bbox_source = "pdfplumber"
#                             except Exception:
#                                 geom_status = "partial"
#                             geom_idx += 1

#                         cells.append({
#                             "row_idx": r_idx, "col_idx": c_idx,
#                             "row_span": 1, "col_span": 1, 
#                             "bbox": cell_bbox, "bbox_source": bbox_source,
#                             "text": str(cell_text).strip() if cell_text is not None else "",
#                             "is_header": r_idx == 0, 
#                             "is_merged": None # Explicitly declaring unproven rather than False
#                         })
                
#                 tables_data.append({
#                     "type": "table", "bbox": bbox, "page_number": page_num,
#                     "extraction_method": "native_pdf", "cells": cells, "_page_height": page_h,
#                     "col_count": len(raw_grid[0]) if isinstance(raw_grid[0], (list, tuple)) else 0,
#                     "geometry_status": geom_status,
#                     "merged_span_status": "unavailable",
#                     "text_status": "available"
#                 })
#         except Exception as e:
#             warnings.append({"page_number": page_num, "component": "table_fatal", "error": f"Table block skipped: {str(e)}"})
            
#         return tables_data, warnings

#     ###########################################################################
#     # 3. PAGE STRATEGY & ISOLATED OCR
#     ###########################################################################

#     def _evaluate_page_strategy(self, page: fitz.Page, blocks: List[Dict]) -> str:
#         if not blocks: return "OCR_ONLY"
        
#         text_chars = 0
#         text_area = 0.0

#         for b in blocks:
#             if b.get("type") == 0:
#                 for l in b.get("lines", []):
#                     for s in l.get("spans", []):
#                         text_chars += len(s.get("text", ""))
                
#                 bbox = b.get("bbox")
#                 if bbox and len(bbox) == 4:
#                     x0, y0, x1, y1 = bbox
#                     if x1 > x0 and y1 > y0:
#                         text_area += (x1 - x0) * (y1 - y0)

#         page_area = page.rect.width * page.rect.height
#         text_coverage = text_area / page_area if page_area > 0 else 0.0

#         img_area = sum((r.x1-r.x0)*(r.y1-r.y0) for img in page.get_images() for r in page.get_image_rects(img[0]))
#         img_coverage = img_area / page_area if page_area > 0 else 0.0

#         if text_chars < 50 and img_coverage > 0.10: return "OCR_ONLY"
#         if text_coverage < 0.005 or img_coverage > 0.30: return "HYBRID"
#         return "NATIVE_ONLY"

#     def _ocr_extract_safely(self, page: fitz.Page, native_bboxes: List[List[float]] = None, native_texts: List[str] = None) -> Tuple[List[Dict], str, str]:
#         """Returns (ocr_elements, status_enum, error_message). Status: success|unavailable|failed"""
#         if not self.ocr_available:
#             return [], "unavailable", "Tesseract executable or python package missing."
            
#         try:
#             pix = page.get_pixmap(dpi=300)
#             img = Image.open(io.BytesIO(pix.tobytes("png")))
#             data = pytesseract.image_to_data(img, config=self.tesseract_config, output_type=Output.DICT)
            
#             blocks, scale = {}, 72.0 / 300.0
#             for i in range(len(data['text'])):
#                 word = data['text'][i].strip()
#                 try: conf = float(data['conf'][i])
#                 except (ValueError, TypeError): continue
                
#                 if conf > 30 and word:
#                     b_id = f"{data['block_num'][i]}_{data['par_num'][i]}_{data['line_num'][i]}"
#                     if b_id not in blocks:
#                         blocks[b_id] = {"text": [], "conf": [], "x0": data['left'][i], "y0": data['top'][i], "x1": data['left'][i]+data['width'][i], "y1": data['top'][i]+data['height'][i]}
#                     else:
#                         b = blocks[b_id]
#                         b["x0"], b["y0"] = min(b["x0"], data['left'][i]), min(b["y0"], data['top'][i])
#                         b["x1"], b["y1"] = max(b["x1"], data['left'][i]+data['width'][i]), max(b["y1"], data['top'][i]+data['height'][i])
#                     blocks[b_id]["text"].append(word)
#                     blocks[b_id]["conf"].append(conf)

#             ocr_elements = []
#             for b in blocks.values():
#                 bbox = self._bbox([b["x0"]*scale, b["y0"]*scale, b["x1"]*scale, b["y1"]*scale])
#                 text = " ".join(b["text"])
                
#                 is_duplicate = False
#                 if native_bboxes and native_texts:
#                     for n_idx, n_box in enumerate(native_bboxes):
#                         if self._calculate_overlap_ratio(bbox, n_box) > 0.5:
#                             if self._token_similarity(text, native_texts[n_idx]) > 0.6:
#                                 is_duplicate = True
#                                 break
                
#                 if not is_duplicate:
#                     ocr_elements.append({
#                         "type": "raw_text", "text": text,
#                         "extraction_method": "ocr", "extraction_confidence": round(statistics.mean(b["conf"])/100.0, 2),
#                         "ocr_status": "success",
#                         "bbox": bbox, "font_size": None, 
#                         "estimated_font_size": round(bbox[3] - bbox[1], 1) if bbox else 12.0, 
#                         "font_source": "ocr_estimate"
#                     })
#             return ocr_elements, "success", ""
#         except Exception as e:
#             logger.error(f"OCR extraction exception: {str(e)}")
#             return [], "failed", str(e)

#     ###########################################################################
#     # 4. SPATIAL LAYOUT & READING ORDER
#     ###########################################################################

#     def _sort_reading_order(self, elements: List[Dict], page_width: float) -> List[Dict]:
#         if not elements: return []
#         full_width, others = [], []
#         for el in elements:
#             if el.get("bbox") and (el["bbox"][2] - el["bbox"][0]) > page_width * 0.70: 
#                 full_width.append(el)
#             else: 
#                 others.append(el)
            
#         full_width.sort(key=lambda e: e["bbox"][1] if e.get("bbox") else 0)
#         final_order, current_y = [], 0.0
        
#         for fw in full_width:
#             band_elements = [e for e in others if e.get("bbox") and e["bbox"][1] >= current_y and e["bbox"][3] <= fw["bbox"][1] + 15]
#             final_order.extend(self._sort_band_columns(band_elements))
#             final_order.append(fw)
#             current_y = fw["bbox"][3]
            
#         remaining = [e for e in others if e.get("bbox") and e["bbox"][1] >= current_y]
#         final_order.extend(self._sort_band_columns(remaining))
#         final_order.extend([e for e in others if not e.get("bbox")])
#         return final_order

#     def _sort_band_columns(self, band_elements: List[Dict]) -> List[Dict]:
#         if not band_elements: return []
#         left_edges = sorted([e["bbox"][0] for e in band_elements if e.get("bbox")])
#         if not left_edges: return band_elements
        
#         column_bounds = []
#         for x0 in left_edges:
#             if not column_bounds or (x0 - column_bounds[-1]["x0"]) > 60:
#                 column_bounds.append({"x0": x0, "elements": []})

#         for el in band_elements:
#             if not el.get("bbox"): continue
#             best_col, min_dist = column_bounds[0], float('inf')
#             cx = (el["bbox"][0] + el["bbox"][2]) / 2
#             for col in column_bounds:
#                 dist = abs(cx - col["x0"]) 
#                 if dist < min_dist: min_dist, best_col = dist, col
#             best_col["elements"].append(el)

#         band_order = []
#         for col in column_bounds:
#             band_order.extend(sorted(col["elements"], key=lambda e: e["bbox"][1]))
#         return band_order

#     ###########################################################################
#     # 5. MASTER EXTRACTION PIPELINE
#     ###########################################################################

#     async def build_structural_tree(self, document_id: str) -> Dict[str, Any]:
#         pdf_path = self._locate_pdf(document_id)
#         folders = self._setup_directories(document_id)
#         pdf_hash = self._hash_content(pdf_path.read_bytes())
        
#         raw_elements, image_assets = [], {}
#         page_metrics, page_warnings, page_failures = [], [], []
#         toc_entries = []

#         stats = {
#             "total_pages": 0, "pages_processed": 0, "pages_with_native_text": 0,
#             "pages_ocr_attempted": 0, "pages_ocr_success": 0, "pages_ocr_unavailable": 0,
#             "pages_ocr_failed": 0, "pages_with_ocr_content": 0,
#             "pages_with_warnings": 0, "pages_failed": 0, "tables_extracted": 0, 
#             "unique_image_assets_extracted": 0, "image_occurrences_extracted": 0
#         }

#         with fitz.open(str(pdf_path)) as doc_fitz, pdfplumber.open(str(pdf_path)) as doc_plumber:
#             stats["total_pages"] = len(doc_fitz)
#             table_of_contents = [{"level": i[0], "title": i[1].strip(), "page_number": i[2]} for i in doc_fitz.get_toc()]
#             toc_entries = [t["title"].lower() for t in table_of_contents if t.get("title")]
            
#             for page_idx in range(stats["total_pages"]):
#                 page_num = page_idx + 1
#                 t_start = time.time()
#                 page_has_warning = False
                
#                 try:
#                     page_fitz = doc_fitz[page_idx]
#                     page_plumber = doc_plumber.pages[page_idx]
#                     page_h, page_w = page_fitz.rect.height, page_fitz.rect.width
#                 except Exception as e:
#                     page_failures.append({"page_number": page_num, "error": f"Fatal page load failure: {str(e)}"})
#                     stats["pages_failed"] += 1
#                     continue
                
#                 page_raw, native_bboxes, native_texts = [], [], []

#                 # 1. STRATEGY EVALUATION (Fault Isolated)
#                 try:
#                     blocks = page_fitz.get_text("dict").get("blocks", [])
#                     strategy = self._evaluate_page_strategy(page_fitz, blocks)
#                 except Exception as e:
#                     page_warnings.append({"page_number": page_num, "component": "strategy", "warning": f"Eval failed: {str(e)}"})
#                     strategy, blocks = "NATIVE_ONLY", []
#                     page_has_warning = True

#                 # 2. TABLES (Fault Isolated)
#                 tables_data, tbl_warnings = self._extract_tables_safely(page_plumber, page_num, page_h)
#                 if tbl_warnings: 
#                     page_warnings.extend(tbl_warnings)
#                     page_has_warning = True
#                 page_raw.extend(tables_data)
#                 stats["tables_extracted"] += len(tables_data)

#                 # 3. IMAGES (Fault Isolated)
#                 try:
#                     for img_info in page_fitz.get_images(full=True):
#                         xref = img_info[0]
#                         base_img = doc_fitz.extract_image(xref)
#                         img_hash = self._hash_content(base_img["image"])[:16]
#                         asset_id = f"asset_{document_id}_{img_hash}"
                        
#                         if asset_id not in image_assets:
#                             img_path = f"{asset_id}.{base_img['ext']}"
#                             with open(folders["assets"] / img_path, "wb") as f: f.write(base_img["image"])
#                             image_assets[asset_id] = {
#                                 "asset_id": asset_id, "xref_original": xref, "hash": img_hash,
#                                 "width": base_img["width"], "height": base_img["height"], 
#                                 "ext": base_img["ext"], "path": f"assets/{img_path}", "occurrence_count": 0
#                             }
#                             stats["unique_image_assets_extracted"] += 1
                        
#                         image_assets[asset_id]["occurrence_count"] += 1
#                         stats["image_occurrences_extracted"] += 1
#                         for rect in page_fitz.get_image_rects(xref):
#                             page_raw.append({
#                                 "type": "image_occurrence", "asset_id": asset_id,
#                                 "bbox": self._bbox([rect.x0, rect.y0, rect.x1, rect.y1]),
#                                 "page_number": page_num, "extraction_method": "native_pdf", "_page_height": page_h
#                             })
#                 except Exception as e:
#                     page_warnings.append({"page_number": page_num, "component": "image", "warning": str(e)})
#                     page_has_warning = True

#                 # 4. NATIVE TEXT (Fault Isolated)
#                 native_extracted = False
#                 if strategy in ["NATIVE_ONLY", "HYBRID"]:
#                     try:
#                         for block in blocks:
#                             if block.get("type") != 0: continue
#                             bbox = self._bbox(block["bbox"])
#                             text, max_font, is_bold, font_name = "", 0.0, False, ""
#                             for l in block.get("lines", []):
#                                 for s in l.get("spans", []):
#                                     text += s.get("text", "")
#                                     max_font = max(max_font, s.get("size", 0))
#                                     font_name = s.get("font", "")
#                                     if (s.get("flags", 0) & 2) or "bold" in font_name.lower(): is_bold = True
#                                 text += " "
                            
#                             text = text.strip()
#                             if text:
#                                 native_bboxes.append(bbox)
#                                 native_texts.append(text)
#                                 native_extracted = True
#                                 page_raw.append({
#                                     "type": "raw_text", "text": text, "font_size": round(max_font, 1),
#                                     "font_family": font_name, "font_source": "native_pdf",
#                                     "is_bold": is_bold, "bbox": bbox, "page_number": page_num,
#                                     "extraction_method": "native_pdf", "_page_height": page_h
#                                 })
#                         if native_extracted: stats["pages_with_native_text"] += 1
#                     except Exception as e:
#                         page_warnings.append({"page_number": page_num, "component": "native_text", "warning": str(e)})
#                         page_has_warning = True

#                 # 5. OCR (Strictly Isolated & Explicit Enum State)
#                 if strategy in ["OCR_ONLY", "HYBRID"]:
#                     stats["pages_ocr_attempted"] += 1
#                     args = (page_fitz,) if strategy == "OCR_ONLY" else (page_fitz, native_bboxes, native_texts)
                    
#                     ocr_blocks, ocr_status, ocr_err = self._ocr_extract_safely(*args)
                    
#                     if ocr_status == "success":
#                         stats["pages_ocr_success"] += 1
#                         if ocr_blocks:
#                             stats["pages_with_ocr_content"] += 1
#                             for b in ocr_blocks:
#                                 b["page_number"] = page_num
#                                 b["_page_height"] = page_h
#                             page_raw.extend(ocr_blocks)
#                     elif ocr_status == "unavailable":
#                         stats["pages_ocr_unavailable"] += 1
#                         # Expected environment state; not logged as an active warning to keep the response clean
#                     elif ocr_status == "failed":
#                         stats["pages_ocr_failed"] += 1
#                         page_warnings.append({"page_number": page_num, "component": "ocr", "warning": f"OCR failed: {ocr_err}"})
#                         page_has_warning = True
                        
#                     # Scanned Degradation State (Recorded without polluting other elements)
#                     if strategy == "OCR_ONLY" and ocr_status != "success":
#                         page_raw.append({
#                             "type": "scanned_page", "bbox": [0.0, 0.0, page_w, page_h],
#                             "page_number": page_num, "text": "", "ocr_status": ocr_status,
#                             "extraction_method": "unavailable", "_page_height": page_h
#                         })

#                 try:
#                     sorted_page = self._sort_reading_order(page_raw, page_w)
#                     raw_elements.extend(sorted_page)
#                 except Exception as e:
#                     page_warnings.append({"page_number": page_num, "component": "layout_sort", "warning": str(e)})
#                     raw_elements.extend(page_raw) 
#                     page_has_warning = True

#                 if page_has_warning: stats["pages_with_warnings"] += 1
#                 stats["pages_processed"] += 1
#                 page_metrics.append({"page": page_num, "strategy": strategy, "duration_sec": round(time.time() - t_start, 2)})

#         # --- PRE-PERSISTENCE: MARK FURNITURE & ASSIGN IDS ---
#         margins = []
#         for el in raw_elements:
#             if el.get("type") == "raw_text" and el.get("bbox"):
#                 y0, y1 = el["bbox"][1], el["bbox"][3]
#                 page_h = el.get("_page_height", 800)
#                 if y1 < page_h * 0.08 or y0 > page_h * 0.92:
#                     margins.append(re.sub(r'\d+', '#', el["text"].strip().lower()))
                    
#         freq, threshold = Counter(margins), max(3, int(stats["total_pages"] * 0.05))
#         for el in raw_elements:
#             el["is_furniture"] = False
#             if el.get("type") == "raw_text" and el.get("bbox"):
#                 y0, y1 = el["bbox"][1], el["bbox"][3]
#                 if y1 < el.get("_page_height", 800) * 0.08 or y0 > el.get("_page_height", 800) * 0.92:
#                     if freq[re.sub(r'\d+', '#', el["text"].strip().lower())] > threshold:
#                         el["is_furniture"] = True

#         doc_seq = 1
#         current_page, page_seq = -1, 1
#         for el in raw_elements:
#             if el["page_number"] != current_page:
#                 current_page, page_seq = el["page_number"], 1
#             el_type_short = el['type'].split('_')[0]
#             el["element_id"] = f"{document_id}_p{current_page}_s{page_seq}_{el_type_short}"
#             el["provenance_id"] = self._generate_provenance_id(pdf_hash, current_page, el.get("bbox"), el["type"], el.get("text", ""), doc_seq)
#             el["document_sequence"] = doc_seq
#             el["page_sequence"] = page_seq
#             doc_seq += 1
#             page_seq += 1

#         with open(folders["root"] / "raw_elements.jsonl", "w") as f:
#             for el in raw_elements: f.write(json.dumps({k:v for k,v in el.items() if not k.startswith("_")}) + "\n")

#         # --- PHASE 2: NORMALIZATION (Deep Copy) ---
#         normalized_elements = [copy.deepcopy(el) for el in raw_elements if not el.get("is_furniture")]
#         base_fonts = [e.get("font_size") for e in normalized_elements if e.get("type") == "raw_text" and e.get("font_size")]
#         median_font = statistics.median(base_fonts) if base_fonts else 12.0
        
#         for el in normalized_elements:
#             if el["type"] == "raw_text":
#                 text = el["text"]
#                 fs = el.get("font_size") or el.get("estimated_font_size", 12.0)
#                 is_bold = el.get("is_bold", False)
#                 has_num = bool(re.match(r'^((Chapter|Section)\s+[IVX\d]+|\d+(\.\d+)+)\b', text, re.IGNORECASE))
                
#                 h_level, h_conf = 0, 1.0
#                 if 0 < len(text.split()) <= 15:
#                     toc_match = any(self._token_similarity(text.lower(), toc) > 0.8 for toc in toc_entries)
#                     if toc_match and (fs > median_font + 1.0 or is_bold or has_num):
#                         h_level, h_conf = 2, 0.95 
#                         if fs > median_font + 2.0: h_level = 1
#                     elif fs > median_font + 3.0:
#                         h_level, h_conf = 1, 0.90
#                     elif (fs > median_font + 1.0) or (is_bold and has_num):
#                         h_level, h_conf = 2, 0.85
                        
#                 if h_level > 0:
#                     el["type"] = "heading"
#                     el["heading_level"] = h_level
#                     el["classification_confidence"] = h_conf
#                 elif re.match(r"^(fig\.?|figure|table|chart)\s*\d+", text, re.IGNORECASE):
#                     el["type"] = "caption"
#                     el["classification_confidence"] = 0.90
#                 else:
#                     el["type"] = "paragraph"

#         # --- PHASE 3: GRAPH EDGES ---
#         graph_nodes, active_path, table_group_counter = [], [], 1
#         page_targets = {}
#         for el in normalized_elements:
#             if el["type"] in ["table", "image_occurrence"]:
#                 page_targets.setdefault(el["page_number"], []).append(el)

#         for i, el in enumerate(normalized_elements):
#             el["previous_element_id"] = normalized_elements[i-1]["element_id"] if i > 0 else None
#             el["next_element_id"] = normalized_elements[i+1]["element_id"] if i < len(normalized_elements)-1 else None
#             el["parent_section_id"], el["caption_element_id"], el["target_element_id"] = None, None, None
#             el["continues_from_element_id"], el["continues_to_element_id"] = None, None

#             if el["type"] == "heading":
#                 level = el["heading_level"]
#                 while active_path and active_path[-1]["level"] >= level: active_path.pop()
#                 active_path.append({"element_id": el["element_id"], "level": level, "text": el["text"]})
            
#             if active_path:
#                 el["parent_section_id"] = active_path[-1]["element_id"]
#                 el["context"] = {
#                     "source": "heading_inheritance",
#                     "path": [dict(p) for p in active_path],
#                     "path_element_ids": [p["element_id"] for p in active_path]
#                 }

#             if el["type"] == "table" and i > 0:
#                 prev = normalized_elements[i-1]
#                 if prev["type"] == "table" and el["page_number"] - prev["page_number"] <= 1:
#                     if prev.get("col_count") == el.get("col_count") and prev.get("bbox") and el.get("bbox"):
#                         if abs(prev["bbox"][0] - el["bbox"][0]) < 20 and abs(prev["bbox"][2] - el["bbox"][2]) < 20:
#                             grp = prev.get("table_group_id", f"tblgrp_{document_id}_{table_group_counter}")
#                             table_group_counter += 1
#                             prev["table_group_id"], el["table_group_id"] = grp, grp
#                             prev["continues_to_element_id"] = el["element_id"]
#                             el["continues_from_element_id"] = prev["element_id"]

#             if el["type"] == "caption" and el.get("bbox"):
#                 best_dist, best_target = float('inf'), None
#                 for target in page_targets.get(el["page_number"], []):
#                     if not target.get("bbox"): continue
#                     cap_center = (el["bbox"][0] + el["bbox"][2]) / 2
#                     tar_center = (target["bbox"][0] + target["bbox"][2]) / 2
#                     if abs(cap_center - tar_center) < 150: 
#                         dy = min(abs(el["bbox"][1] - target["bbox"][3]), abs(target["bbox"][1] - el["bbox"][3]))
#                         if dy < best_dist and dy < 150: 
#                             best_dist, best_target = dy, target
#                 if best_target:
#                     el["target_element_id"] = best_target["element_id"]
#                     best_target["caption_element_id"] = el["element_id"]

#             graph_nodes.append({
#                 "element_id": el["element_id"], "provenance_id": el["provenance_id"],
#                 "parent_section_id": el.get("parent_section_id"), "previous_element_id": el.get("previous_element_id"),
#                 "next_element_id": el.get("next_element_id"), "caption_element_id": el.get("caption_element_id"),
#                 "target_element_id": el.get("target_element_id"), "continues_from_element_id": el.get("continues_from_element_id"),
#                 "continues_to_element_id": el.get("continues_to_element_id")
#             })

#         # --- PHASE 4: PERSISTENCE & COMPLIANT API RETURN ---
#         manifest = {
#             "document_id": document_id, "schema_version": self.schema_version,
#             "extraction_version": self.extraction_version, "source_pdf_hash": pdf_hash,
#             "ocr_health": {
#                 "provider": "tesseract", "python_package_available": PYTESSERACT_AVAILABLE,
#                 "executable_available": self.tesseract_exe_found, "available": self.ocr_available,
#                 "reason": "tesseract_executable_not_found" if not self.tesseract_exe_found else "ok"
#             },
#             "extraction_summary": stats,
#             "page_failures": page_failures, "page_warnings": page_warnings,
#             "page_metrics": page_metrics
#         }

#         with open(folders["root"] / "manifest.json", "w") as f: json.dump(manifest, f, indent=2)
#         with open(folders["root"] / "assets_manifest.json", "w") as f: json.dump(list(image_assets.values()), f, indent=2)
#         with open(folders["root"] / "normalized_elements.jsonl", "w") as f:
#             for el in normalized_elements: f.write(json.dumps({k:v for k,v in el.items() if not k.startswith("_")}) + "\n")
#         with open(folders["root"] / "structural_graph.json", "w") as f: json.dump(graph_nodes, f, indent=2)

#         summary = {
#             "success": True, "message": "Structure extraction complete.",
#             "data": {
#                 "manifest": manifest,
#                 "data_locations": {
#                     "raw": f"/storage/processed/{document_id}/raw_elements.jsonl",
#                     "normalized": f"/storage/processed/{document_id}/normalized_elements.jsonl",
#                     "graph": f"/storage/processed/{document_id}/structural_graph.json",
#                     "assets": f"/storage/processed/{document_id}/assets_manifest.json"
#                 }
#             }
#         }
#         logger.info(f"Structure extraction and provenance established for {document_id}")
#         return summary













# import io
# import json
# import re
# import hashlib
# import statistics
# import copy
# import time
# import shutil
# from collections import Counter
# from pathlib import Path
# from typing import Any, Dict, List, Tuple

# import pymupdf as fitz
# import pdfplumber
# from PIL import Image

# try:
#     import pytesseract
#     from pytesseract import Output
#     PYTESSERACT_AVAILABLE = True
# except ImportError:
#     PYTESSERACT_AVAILABLE = False

# from app.core.config import settings
# from app.core.logger import logger


# class StructureService:
#     def __init__(self):
#         self.raw_dir = settings.STORAGE_RAW_DIR
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR
#         self.tesseract_config = "--oem 3 --psm 3"
#         self.schema_version = "1.7"
#         self.extraction_version = "structure-v11-rc"
        
#         # Deterministic OCR Backend Check
#         self.tesseract_exe_found = shutil.which("tesseract") is not None
#         self.ocr_available = PYTESSERACT_AVAILABLE and self.tesseract_exe_found
        
#         if not self.ocr_available:
#             logger.warning("OCR backend: Tesseract executable unavailable. OCR fallback disabled.")
#         else:
#             logger.info("OCR backend: Tesseract available and verified in PATH.")

#     ###########################################################################
#     # 1. IO, GEOMETRY, & HASHING
#     ###########################################################################

#     def _locate_pdf(self, document_id: str) -> Path:
#         for p in [self.raw_dir / document_id / "original.pdf", self.raw_dir / f"{document_id}.pdf"]:
#             if p.exists(): return p
#         raise FileNotFoundError(f"PDF document not found for ID: {document_id}")

#     def _setup_directories(self, document_id: str) -> Dict[str, Path]:
#         root = self.processed_dir / document_id
#         folders = {"root": root, "assets": root / "assets"}
#         for f in folders.values(): f.mkdir(parents=True, exist_ok=True)
#         return folders

#     def _hash_content(self, data: bytes) -> str:
#         return hashlib.sha256(data).hexdigest()

#     def _generate_provenance_id(self, doc_hash: str, page: int, bbox: List[float], el_type: str, content: str, index: int) -> str:
#         content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()[:12] if content else "empty"
#         bbox_str = f"{round(bbox[0],1)}_{round(bbox[1],1)}_{round(bbox[2],1)}_{round(bbox[3],1)}" if bbox else "none"
#         sig = f"{doc_hash}|p{page}|type:{el_type}|box:{bbox_str}|c:{content_hash}|idx:{index}"
#         return hashlib.sha256(sig.encode('utf-8')).hexdigest()

#     def _bbox(self, bbox) -> List[float]:
#         if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
#             return None
#         try:
#             return [round(float(x), 2) for x in bbox]
#         except (ValueError, TypeError):
#             return None

#     def _calculate_overlap_ratio(self, box1: List[float], box2: List[float]) -> float:
#         if not box1 or not box2: return 0.0
#         dx = min(box1[2], box2[2]) - max(box1[0], box2[0])
#         dy = min(box1[3], box2[3]) - max(box1[1], box2[1])
#         if dx > 0 and dy > 0:
#             overlap_area = dx * dy
#             area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
#             return overlap_area / area1 if area1 > 0 else 0.0
#         return 0.0

#     def _token_similarity(self, text1: str, text2: str) -> float:
#         t1 = set(re.findall(r'\w+', text1.lower()))
#         t2 = set(re.findall(r'\w+', text2.lower()))
#         if not t1 or not t2: return 0.0
#         return len(t1 & t2) / len(t1 | t2)

#     ###########################################################################
#     # 2. ISOLATED COMPONENT: SAFE TABLE EXTRACTION
#     ###########################################################################

#     def _extract_tables_safely(self, page_plumber, page_num: int, page_h: float) -> Tuple[List[Dict], List[Dict]]:
#         """Text grid is the source of truth. Geometry is mapped ONLY if perfectly aligned."""
#         tables_data, warnings = [], []
        
#         try:
#             for table_obj in page_plumber.find_tables():
#                 try:
#                     raw_grid = table_obj.extract()
#                 except Exception as e:
#                     warnings.append({"page_number": page_num, "component": "table", "warning": f"Grid text extraction failed: {str(e)}"})
#                     continue

#                 if not isinstance(raw_grid, list) or not raw_grid:
#                     warnings.append({"page_number": page_num, "component": "table", "warning": "Extracted grid is empty or malformed."})
#                     continue

#                 bbox = self._bbox(table_obj.bbox) if hasattr(table_obj, "bbox") else None
#                 cells = []
#                 geom_status = "unavailable"
                
#                 # Independent Geometry Attempt
#                 valid_cells_geom = getattr(table_obj, "cells", [])
#                 total_grid_cells = sum(len(row) for row in raw_grid if isinstance(row, (list, tuple)))
                
#                 can_map_1_to_1 = isinstance(valid_cells_geom, list) and len(valid_cells_geom) == total_grid_cells
#                 if can_map_1_to_1:
#                     geom_status = "available"
#                 else:
#                     warnings.append({"page_number": page_num, "component": "table_geometry", "warning": "Geometry length mismatch. Bboxes set to null to protect text integrity."})

#                 geom_idx = 0
#                 for r_idx, row in enumerate(raw_grid):
#                     if not isinstance(row, (list, tuple)): 
#                         row = [str(row)] 
                        
#                     for c_idx, cell_text in enumerate(row):
#                         cell_bbox, bbox_source = None, "unavailable"
                        
#                         if can_map_1_to_1:
#                             try:
#                                 c_geom = valid_cells_geom[geom_idx]
#                                 parsed_bbox = self._bbox(c_geom)
#                                 if parsed_bbox:
#                                     cell_bbox = parsed_bbox
#                                     bbox_source = "pdfplumber"
#                             except Exception:
#                                 geom_status = "partial"
#                             geom_idx += 1

#                         cells.append({
#                             "row_idx": r_idx, "col_idx": c_idx,
#                             "row_span": 1, "col_span": 1, 
#                             "bbox": cell_bbox, "bbox_source": bbox_source,
#                             "text": str(cell_text).strip() if cell_text is not None else "",
#                             "is_header": r_idx == 0, 
#                             "is_merged": None # Explicitly declaring unproven rather than False
#                         })
                
#                 tables_data.append({
#                     "type": "table", "bbox": bbox, "page_number": page_num,
#                     "extraction_method": "native_pdf", "cells": cells, "_page_height": page_h,
#                     "col_count": len(raw_grid[0]) if isinstance(raw_grid[0], (list, tuple)) else 0,
#                     "geometry_status": geom_status,
#                     "merged_span_status": "unavailable",
#                     "text_status": "available"
#                 })
#         except Exception as e:
#             warnings.append({"page_number": page_num, "component": "table_fatal", "warning": f"Table block skipped: {str(e)}"})
            
#         return tables_data, warnings

#     ###########################################################################
#     # 3. PAGE STRATEGY & ISOLATED OCR
#     ###########################################################################

#     def _evaluate_page_strategy(self, page: fitz.Page, blocks: List[Dict]) -> str:
#         if not blocks: return "OCR_ONLY"
        
#         text_chars = 0
#         text_area = 0.0

#         for b in blocks:
#             if b.get("type") == 0:
#                 for l in b.get("lines", []):
#                     for s in l.get("spans", []):
#                         text_chars += len(s.get("text", ""))
                
#                 bbox = b.get("bbox")
#                 if bbox and len(bbox) == 4:
#                     x0, y0, x1, y1 = bbox
#                     if x1 > x0 and y1 > y0:
#                         text_area += (x1 - x0) * (y1 - y0)

#         page_area = page.rect.width * page.rect.height
#         text_coverage = text_area / page_area if page_area > 0 else 0.0

#         img_area = sum((r.x1-r.x0)*(r.y1-r.y0) for img in page.get_images() for r in page.get_image_rects(img[0]))
#         img_coverage = img_area / page_area if page_area > 0 else 0.0

#         if text_chars < 50 and img_coverage > 0.10: return "OCR_ONLY"
#         if text_coverage < 0.005 or img_coverage > 0.30: return "HYBRID"
#         return "NATIVE_ONLY"

#     def _ocr_extract_safely(self, page: fitz.Page, native_bboxes: List[List[float]] = None, native_texts: List[str] = None) -> Tuple[List[Dict], str, str]:
#         """Returns (ocr_elements, status_enum, error_message). Status: success|unavailable|failed"""
#         if not self.ocr_available:
#             return [], "unavailable", "Tesseract executable or python package missing."
            
#         try:
#             pix = page.get_pixmap(dpi=300)
#             img = Image.open(io.BytesIO(pix.tobytes("png")))
#             data = pytesseract.image_to_data(img, config=self.tesseract_config, output_type=Output.DICT)
            
#             blocks, scale = {}, 72.0 / 300.0
#             for i in range(len(data['text'])):
#                 word = data['text'][i].strip()
#                 try: conf = float(data['conf'][i])
#                 except (ValueError, TypeError): continue
                
#                 if conf > 30 and word:
#                     b_id = f"{data['block_num'][i]}_{data['par_num'][i]}_{data['line_num'][i]}"
#                     if b_id not in blocks:
#                         blocks[b_id] = {"text": [], "conf": [], "x0": data['left'][i], "y0": data['top'][i], "x1": data['left'][i]+data['width'][i], "y1": data['top'][i]+data['height'][i]}
#                     else:
#                         b = blocks[b_id]
#                         b["x0"], b["y0"] = min(b["x0"], data['left'][i]), min(b["y0"], data['top'][i])
#                         b["x1"], b["y1"] = max(b["x1"], data['left'][i]+data['width'][i]), max(b["y1"], data['top'][i]+data['height'][i])
#                     blocks[b_id]["text"].append(word)
#                     blocks[b_id]["conf"].append(conf)

#             ocr_elements = []
#             for b in blocks.values():
#                 bbox = self._bbox([b["x0"]*scale, b["y0"]*scale, b["x1"]*scale, b["y1"]*scale])
#                 text = " ".join(b["text"])
                
#                 is_duplicate = False
#                 if native_bboxes and native_texts:
#                     for n_idx, n_box in enumerate(native_bboxes):
#                         if self._calculate_overlap_ratio(bbox, n_box) > 0.5:
#                             if self._token_similarity(text, native_texts[n_idx]) > 0.6:
#                                 is_duplicate = True
#                                 break
                
#                 if not is_duplicate:
#                     ocr_elements.append({
#                         "type": "raw_text", "text": text,
#                         "extraction_method": "ocr", "extraction_confidence": round(statistics.mean(b["conf"])/100.0, 2),
#                         "ocr_status": "success",
#                         "bbox": bbox, "font_size": None, 
#                         "estimated_font_size": round(bbox[3] - bbox[1], 1) if bbox else 12.0, 
#                         "font_source": "ocr_estimate"
#                     })
#             return ocr_elements, "success", ""
#         except Exception as e:
#             logger.error(f"OCR extraction exception: {str(e)}")
#             return [], "failed", str(e)

#     ###########################################################################
#     # 4. SPATIAL LAYOUT & READING ORDER
#     ###########################################################################

#     def _sort_reading_order(self, elements: List[Dict], page_width: float) -> List[Dict]:
#         if not elements: return []
#         full_width, others = [], []
#         for el in elements:
#             if el.get("bbox") and (el["bbox"][2] - el["bbox"][0]) > page_width * 0.70: 
#                 full_width.append(el)
#             else: 
#                 others.append(el)
            
#         full_width.sort(key=lambda e: e["bbox"][1] if e.get("bbox") else 0)
#         final_order, current_y = [], 0.0
        
#         for fw in full_width:
#             band_elements = [e for e in others if e.get("bbox") and e["bbox"][1] >= current_y and e["bbox"][3] <= fw["bbox"][1] + 15]
#             final_order.extend(self._sort_band_columns(band_elements))
#             final_order.append(fw)
#             current_y = fw["bbox"][3]
            
#         remaining = [e for e in others if e.get("bbox") and e["bbox"][1] >= current_y]
#         final_order.extend(self._sort_band_columns(remaining))
#         final_order.extend([e for e in others if not e.get("bbox")])
#         return final_order

#     def _sort_band_columns(self, band_elements: List[Dict]) -> List[Dict]:
#         if not band_elements: return []
#         left_edges = sorted([e["bbox"][0] for e in band_elements if e.get("bbox")])
#         if not left_edges: return band_elements
        
#         column_bounds = []
#         for x0 in left_edges:
#             if not column_bounds or (x0 - column_bounds[-1]["x0"]) > 60:
#                 column_bounds.append({"x0": x0, "elements": []})

#         for el in band_elements:
#             if not el.get("bbox"): continue
#             best_col, min_dist = column_bounds[0], float('inf')
#             cx = (el["bbox"][0] + el["bbox"][2]) / 2
#             for col in column_bounds:
#                 dist = abs(cx - col["x0"]) 
#                 if dist < min_dist: min_dist, best_col = dist, col
#             best_col["elements"].append(el)

#         band_order = []
#         for col in column_bounds:
#             band_order.extend(sorted(col["elements"], key=lambda e: e["bbox"][1]))
#         return band_order

#     ###########################################################################
#     # 5. MASTER EXTRACTION PIPELINE
#     ###########################################################################

#     async def build_structural_tree(self, document_id: str) -> Dict[str, Any]:
#         pdf_path = self._locate_pdf(document_id)
#         folders = self._setup_directories(document_id)
#         pdf_hash = self._hash_content(pdf_path.read_bytes())
        
#         raw_elements, image_assets = [], {}
#         page_metrics, page_warnings, page_failures = [], [] ,[]
#         toc_entries = []

#         stats = {
#             "total_pages": 0, "pages_processed": 0, "pages_with_native_text": 0,
#             "pages_ocr_attempted": 0, "pages_ocr_success": 0, "pages_ocr_unavailable": 0,
#             "pages_ocr_failed": 0, "pages_with_ocr_content": 0,
#             "pages_with_warnings": 0, "pages_failed": 0, "tables_extracted": 0, 
#             "unique_image_assets_extracted": 0, "image_occurrences_extracted": 0
#         }

#         with fitz.open(str(pdf_path)) as doc_fitz, pdfplumber.open(str(pdf_path)) as doc_plumber:
#             stats["total_pages"] = len(doc_fitz)
#             table_of_contents = [{"level": i[0], "title": i[1].strip(), "page_number": i[2]} for i in doc_fitz.get_toc()]
#             toc_entries = [t["title"].lower() for t in table_of_contents if t.get("title")]
            
#             for page_idx in range(stats["total_pages"]):
#                 page_num = page_idx + 1
#                 t_start = time.time()
#                 page_has_warning = False
                
#                 try:
#                     page_fitz = doc_fitz[page_idx]
#                     page_plumber = doc_plumber.pages[page_idx]
#                     page_h, page_w = page_fitz.rect.height, page_fitz.rect.width
#                 except Exception as e:
#                     page_failures.append({"page_number": page_num, "error": f"Fatal page load failure: {str(e)}"})
#                     stats["pages_failed"] += 1
#                     continue
                
#                 page_raw, native_bboxes, native_texts = [], [], []

#                 # 1. STRATEGY EVALUATION (Fault Isolated)
#                 try:
#                     blocks = page_fitz.get_text("dict").get("blocks", [])
#                     strategy = self._evaluate_page_strategy(page_fitz, blocks)
#                 except Exception as e:
#                     page_warnings.append({"page_number": page_num, "component": "strategy", "warning": f"Eval failed: {str(e)}"})
#                     strategy, blocks = "NATIVE_ONLY", []
#                     page_has_warning = True

#                 # 2. TABLES (Fault Isolated)
#                 tables_data, tbl_warnings = self._extract_tables_safely(page_plumber, page_num, page_h)
#                 if tbl_warnings: 
#                     page_warnings.extend(tbl_warnings)
#                     page_has_warning = True
#                 page_raw.extend(tables_data)
#                 stats["tables_extracted"] += len(tables_data)

#                 # 3. IMAGES (Fault Isolated)
#                 try:
#                     for img_info in page_fitz.get_images(full=True):
#                         xref = img_info[0]
#                         base_img = doc_fitz.extract_image(xref)
#                         img_hash = self._hash_content(base_img["image"])[:16]
#                         asset_id = f"asset_{document_id}_{img_hash}"
                        
#                         if asset_id not in image_assets:
#                             img_path = f"{asset_id}.{base_img['ext']}"
#                             with open(folders["assets"] / img_path, "wb") as f: f.write(base_img["image"])
#                             image_assets[asset_id] = {
#                                 "asset_id": asset_id, "xref_original": xref, "hash": img_hash,
#                                 "width": base_img["width"], "height": base_img["height"], 
#                                 "ext": base_img["ext"], "path": f"assets/{img_path}", "occurrence_count": 0
#                             }
#                             stats["unique_image_assets_extracted"] += 1
                        
#                         image_assets[asset_id]["occurrence_count"] += 1
#                         stats["image_occurrences_extracted"] += 1
#                         for rect in page_fitz.get_image_rects(xref):
#                             page_raw.append({
#                                 "type": "image_occurrence", "asset_id": asset_id,
#                                 "bbox": self._bbox([rect.x0, rect.y0, rect.x1, rect.y1]),
#                                 "page_number": page_num, "extraction_method": "native_pdf", "_page_height": page_h
#                             })
#                 except Exception as e:
#                     page_warnings.append({"page_number": page_num, "component": "image", "warning": str(e)})
#                     page_has_warning = True

#                 # 4. NATIVE TEXT (Fault Isolated)
#                 native_extracted = False
#                 if strategy in ["NATIVE_ONLY", "HYBRID"]:
#                     try:
#                         for block in blocks:
#                             if block.get("type") != 0: continue
#                             bbox = self._bbox(block["bbox"])
#                             text, max_font, is_bold, font_name = "", 0.0, False, ""
#                             for l in block.get("lines", []):
#                                 for s in l.get("spans", []):
#                                     text += s.get("text", "")
#                                     max_font = max(max_font, s.get("size", 0))
#                                     font_name = s.get("font", "")
#                                     if (s.get("flags", 0) & 2) or "bold" in font_name.lower(): is_bold = True
#                                 text += " "
                            
#                             text = text.strip()
#                             if text:
#                                 native_bboxes.append(bbox)
#                                 native_texts.append(text)
#                                 native_extracted = True
#                                 page_raw.append({
#                                     "type": "raw_text", "text": text, "font_size": round(max_font, 1),
#                                     "font_family": font_name, "font_source": "native_pdf",
#                                     "is_bold": is_bold, "bbox": bbox, "page_number": page_num,
#                                     "extraction_method": "native_pdf", "_page_height": page_h
#                                 })
#                         if native_extracted: stats["pages_with_native_text"] += 1
#                     except Exception as e:
#                         page_warnings.append({"page_number": page_num, "component": "native_text", "warning": str(e)})
#                         page_has_warning = True

#                 # 5. OCR (Strictly Isolated)
#                 if strategy in ["OCR_ONLY", "HYBRID"]:
#                     stats["pages_ocr_attempted"] += 1
#                     args = (page_fitz,) if strategy == "OCR_ONLY" else (page_fitz, native_bboxes, native_texts)
                    
#                     ocr_blocks, ocr_status, ocr_err = self._ocr_extract_safely(*args)
                    
#                     if ocr_status == "success":
#                         stats["pages_ocr_success"] += 1
#                         if ocr_blocks:
#                             stats["pages_with_ocr_content"] += 1
#                             for b in ocr_blocks:
#                                 b["page_number"] = page_num
#                                 b["_page_height"] = page_h
#                             page_raw.extend(ocr_blocks)
#                     elif ocr_status == "unavailable":
#                         stats["pages_ocr_unavailable"] += 1
#                         page_warnings.append({"page_number": page_num, "component": "ocr", "warning": "Tesseract unavailable"})
#                         page_has_warning = True
#                     elif ocr_status == "failed":
#                         stats["pages_ocr_failed"] += 1
#                         page_warnings.append({"page_number": page_num, "component": "ocr", "warning": f"OCR failed: {ocr_err}"})
#                         page_has_warning = True
                        
#                     if strategy == "OCR_ONLY" and ocr_status != "success":
#                         page_raw.append({
#                             "type": "scanned_page", "bbox": [0.0, 0.0, page_w, page_h],
#                             "page_number": page_num, "text": "", "ocr_status": ocr_status,
#                             "extraction_method": "unavailable", "_page_height": page_h
#                         })

#                 try:
#                     sorted_page = self._sort_reading_order(page_raw, page_w)
#                     raw_elements.extend(sorted_page)
#                 except Exception as e:
#                     page_warnings.append({"page_number": page_num, "component": "layout_sort", "warning": str(e)})
#                     raw_elements.extend(page_raw) 
#                     page_has_warning = True

#                 if page_has_warning: stats["pages_with_warnings"] += 1
#                 stats["pages_processed"] += 1
#                 page_metrics.append({"page": page_num, "strategy": strategy, "duration_sec": round(time.time() - t_start, 2)})

#         # --- PRE-PERSISTENCE: MARK FURNITURE & ASSIGN IDS ---
#         margins = []
#         for el in raw_elements:
#             if el.get("type") == "raw_text" and el.get("bbox"):
#                 y0, y1 = el["bbox"][1], el["bbox"][3]
#                 page_h = el.get("_page_height", 800)
#                 if y1 < page_h * 0.08 or y0 > page_h * 0.92:
#                     margins.append(re.sub(r'\d+', '#', el["text"].strip().lower()))
                    
#         freq, threshold = Counter(margins), max(3, int(stats["total_pages"] * 0.05))
#         for el in raw_elements:
#             el["is_furniture"] = False
#             if el.get("type") == "raw_text" and el.get("bbox"):
#                 y0, y1 = el["bbox"][1], el["bbox"][3]
#                 if y1 < el.get("_page_height", 800) * 0.08 or y0 > el.get("_page_height", 800) * 0.92:
#                     if freq[re.sub(r'\d+', '#', el["text"].strip().lower())] > threshold:
#                         el["is_furniture"] = True

#         doc_seq = 1
#         current_page, page_seq = -1, 1
#         for el in raw_elements:
#             if el["page_number"] != current_page:
#                 current_page, page_seq = el["page_number"], 1
#             el_type_short = el['type'].split('_')[0]
#             el["element_id"] = f"{document_id}_p{current_page}_s{page_seq}_{el_type_short}"
#             el["provenance_id"] = self._generate_provenance_id(pdf_hash, current_page, el.get("bbox"), el["type"], el.get("text", ""), doc_seq)
#             el["document_sequence"] = doc_seq
#             el["page_sequence"] = page_seq
#             doc_seq += 1
#             page_seq += 1

#         with open(folders["root"] / "raw_elements.jsonl", "w") as f:
#             for el in raw_elements: f.write(json.dumps({k:v for k,v in el.items() if not k.startswith("_")}) + "\n")

#         # --- PHASE 2: NORMALIZATION (Deep Copy) ---
#         normalized_elements = [copy.deepcopy(el) for el in raw_elements if not el.get("is_furniture")]
#         base_fonts = [e.get("font_size") for e in normalized_elements if e.get("type") == "raw_text" and e.get("font_size")]
#         median_font = statistics.median(base_fonts) if base_fonts else 12.0
        
#         for el in normalized_elements:
#             if el["type"] == "raw_text":
#                 text = el["text"]
#                 fs = el.get("font_size") or el.get("estimated_font_size", 12.0)
#                 is_bold = el.get("is_bold", False)
#                 has_num = bool(re.match(r'^((Chapter|Section)\s+[IVX\d]+|\d+(\.\d+)+)\b', text, re.IGNORECASE))
                
#                 h_level, h_conf = 0, 1.0
#                 if 0 < len(text.split()) <= 15:
#                     toc_match = any(self._token_similarity(text.lower(), toc) > 0.8 for toc in toc_entries)
#                     if toc_match and (fs > median_font + 1.0 or is_bold or has_num):
#                         h_level, h_conf = 2, 0.95 
#                         if fs > median_font + 2.0: h_level = 1
#                     elif fs > median_font + 3.0:
#                         h_level, h_conf = 1, 0.90
#                     elif (fs > median_font + 1.0) or (is_bold and has_num):
#                         h_level, h_conf = 2, 0.85
                        
#                 if h_level > 0:
#                     el["type"] = "heading"
#                     el["heading_level"] = h_level
#                     el["classification_confidence"] = h_conf
#                 elif re.match(r"^(fig\.?|figure|table|chart)\s*\d+", text, re.IGNORECASE):
#                     el["type"] = "caption"
#                     el["classification_confidence"] = 0.90
#                 else:
#                     el["type"] = "paragraph"

#         # --- PHASE 3: GRAPH EDGES ---
#         graph_nodes, active_path, table_group_counter = [], [], 1
#         page_targets = {}
#         for el in normalized_elements:
#             if el["type"] in ["table", "image_occurrence"]:
#                 page_targets.setdefault(el["page_number"], []).append(el)

#         for i, el in enumerate(normalized_elements):
#             el["previous_element_id"] = normalized_elements[i-1]["element_id"] if i > 0 else None
#             el["next_element_id"] = normalized_elements[i+1]["element_id"] if i < len(normalized_elements)-1 else None
#             el["parent_section_id"], el["caption_element_id"], el["target_element_id"] = None, None, None
#             el["continues_from_element_id"], el["continues_to_element_id"] = None, None

#             if el["type"] == "heading":
#                 level = el["heading_level"]
#                 while active_path and active_path[-1]["level"] >= level: active_path.pop()
#                 active_path.append({"element_id": el["element_id"], "level": level, "text": el["text"]})
            
#             if active_path:
#                 el["parent_section_id"] = active_path[-1]["element_id"]
#                 el["context"] = {
#                     "source": "heading_inheritance",
#                     "path": [dict(p) for p in active_path],
#                     "path_element_ids": [p["element_id"] for p in active_path]
#                 }

#             if el["type"] == "table" and i > 0:
#                 prev = normalized_elements[i-1]
#                 if prev["type"] == "table" and el["page_number"] - prev["page_number"] <= 1:
#                     if prev.get("col_count") == el.get("col_count") and prev.get("bbox") and el.get("bbox"):
#                         if abs(prev["bbox"][0] - el["bbox"][0]) < 20 and abs(prev["bbox"][2] - el["bbox"][2]) < 20:
#                             grp = prev.get("table_group_id", f"tblgrp_{document_id}_{table_group_counter}")
#                             table_group_counter += 1
#                             prev["table_group_id"], el["table_group_id"] = grp, grp
#                             prev["continues_to_element_id"] = el["element_id"]
#                             el["continues_from_element_id"] = prev["element_id"]

#             if el["type"] == "caption" and el.get("bbox"):
#                 best_dist, best_target = float('inf'), None
#                 for target in page_targets.get(el["page_number"], []):
#                     if not target.get("bbox"): continue
#                     cap_center = (el["bbox"][0] + el["bbox"][2]) / 2
#                     tar_center = (target["bbox"][0] + target["bbox"][2]) / 2
#                     if abs(cap_center - tar_center) < 150: 
#                         dy = min(abs(el["bbox"][1] - target["bbox"][3]), abs(target["bbox"][1] - el["bbox"][3]))
#                         if dy < best_dist and dy < 150: 
#                             best_dist, best_target = dy, target
#                 if best_target:
#                     el["target_element_id"] = best_target["element_id"]
#                     best_target["caption_element_id"] = el["element_id"]

#             graph_nodes.append({
#                 "element_id": el["element_id"], "provenance_id": el["provenance_id"],
#                 "parent_section_id": el.get("parent_section_id"), "previous_element_id": el.get("previous_element_id"),
#                 "next_element_id": el.get("next_element_id"), "caption_element_id": el.get("caption_element_id"),
#                 "target_element_id": el.get("target_element_id"), "continues_from_element_id": el.get("continues_from_element_id"),
#                 "continues_to_element_id": el.get("continues_to_element_id")
#             })

#         # --- PHASE 4: PERSISTENCE & COMPLIANT API RETURN ---
#         manifest = {
#             "document_id": document_id, "schema_version": self.schema_version,
#             "extraction_version": self.extraction_version, "source_pdf_hash": pdf_hash,
#             "ocr_health": {
#                 "provider": "tesseract", "python_package_available": PYTESSERACT_AVAILABLE,
#                 "executable_available": self.tesseract_exe_found, "available": self.ocr_available,
#                 "reason": "tesseract_executable_not_found" if not self.tesseract_exe_found else "ok"
#             },
#             "extraction_summary": stats,
#             "page_failures": page_failures, "page_warnings": page_warnings,
#             "page_metrics": page_metrics
#         }

#         with open(folders["root"] / "manifest.json", "w") as f: json.dump(manifest, f, indent=2)
#         with open(folders["root"] / "assets_manifest.json", "w") as f: json.dump(list(image_assets.values()), f, indent=2)
#         with open(folders["root"] / "normalized_elements.jsonl", "w") as f:
#             for el in normalized_elements: f.write(json.dumps({k:v for k,v in el.items() if not k.startswith("_")}) + "\n")
#         with open(folders["root"] / "structural_graph.json", "w") as f: json.dump(graph_nodes, f, indent=2)

#         summary = {
#             "success": True, "message": "Structure extraction complete.",
#             "data": {
#                 "manifest": manifest,
#                 "data_locations": {
#                     "raw": f"/storage/processed/{document_id}/raw_elements.jsonl",
#                     "normalized": f"/storage/processed/{document_id}/normalized_elements.jsonl",
#                     "graph": f"/storage/processed/{document_id}/structural_graph.json",
#                     "assets": f"/storage/processed/{document_id}/assets_manifest.json"
#                 }
#             }
#         }
#         logger.info(f"Structure extraction and provenance established for {document_id}")
#         return summary














import io
import json
import re
import math
import hashlib
import statistics
import copy
import time
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pymupdf as fitz
import pdfplumber
from PIL import Image

try:
    import pytesseract
    from pytesseract import Output
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

from app.core.config import settings
from app.core.logger import logger


class StructureService:
    def __init__(self):
        self.raw_dir = settings.STORAGE_RAW_DIR
        self.processed_dir = settings.STORAGE_PROCESSED_DIR
        self.tesseract_config = "--oem 3 --psm 3"
        self.schema_version = "1.7"
        self.extraction_version = "structure-v11-rc"
        
        # Deterministic OCR Backend Check
        self.tesseract_exe_found = shutil.which("tesseract") is not None
        self.ocr_available = PYTESSERACT_AVAILABLE and self.tesseract_exe_found
        
        if not self.ocr_available:
            logger.warning("OCR backend: Tesseract executable unavailable. OCR fallback disabled.")
        else:
            logger.info("OCR backend: Tesseract available and verified in PATH.")

    ###########################################################################
    # 1. IO, GEOMETRY, & HASHING
    ###########################################################################

    def _locate_pdf(self, document_id: str) -> Path:
        for p in [self.raw_dir / document_id / "original.pdf", self.raw_dir / f"{document_id}.pdf"]:
            if p.exists(): return p
        raise FileNotFoundError(f"PDF document not found for ID: {document_id}")

    def _setup_directories(self, document_id: str) -> Dict[str, Path]:
        root = self.processed_dir / document_id
        folders = {"root": root, "assets": root / "assets"}
        for f in folders.values(): f.mkdir(parents=True, exist_ok=True)
        return folders

    def _hash_content(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _generate_provenance_id(self, doc_hash: str, page: int, bbox: List[float], el_type: str, content: str, index: int) -> str:
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()[:12] if content else "empty"
        bbox_str = f"{round(bbox[0],1)}_{round(bbox[1],1)}_{round(bbox[2],1)}_{round(bbox[3],1)}" if bbox else "none"
        sig = f"{doc_hash}|p{page}|type:{el_type}|box:{bbox_str}|c:{content_hash}|idx:{index}"
        return hashlib.sha256(sig.encode('utf-8')).hexdigest()

    def _bbox(self, bbox) -> List[float]:
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            return None
        try:
            return [round(float(x), 2) for x in bbox]
        except (ValueError, TypeError):
            return None

    def _calculate_overlap_ratio(self, box1: List[float], box2: List[float]) -> float:
        if not box1 or not box2: return 0.0
        dx = min(box1[2], box2[2]) - max(box1[0], box2[0])
        dy = min(box1[3], box2[3]) - max(box1[1], box2[1])
        if dx > 0 and dy > 0:
            overlap_area = dx * dy
            area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
            return overlap_area / area1 if area1 > 0 else 0.0
        return 0.0

    def _token_similarity(self, text1: str, text2: str) -> float:
        t1 = set(re.findall(r'\w+', text1.lower()))
        t2 = set(re.findall(r'\w+', text2.lower()))
        if not t1 or not t2: return 0.0
        return len(t1 & t2) / len(t1 | t2)

    ###########################################################################
    # 2. ISOLATED COMPONENT: SAFE TABLE EXTRACTION
    ###########################################################################

    def _extract_tables_safely(self, page_plumber, page_num: int, page_h: float) -> Tuple[List[Dict], List[Dict]]:
        tables_data, warnings = [], []
        
        try:
            for table_obj in page_plumber.find_tables():
                try:
                    raw_grid = table_obj.extract()
                except Exception as e:
                    warnings.append({"page_number": page_num, "component": "table", "warning": f"Grid text extraction failed: {str(e)}"})
                    continue

                if not isinstance(raw_grid, list) or not raw_grid:
                    warnings.append({"page_number": page_num, "component": "table", "warning": "Extracted grid is empty or malformed."})
                    continue

                bbox = self._bbox(table_obj.bbox) if hasattr(table_obj, "bbox") else None
                cells = []
                geom_status = "unavailable"
                
                # Independent Geometry Attempt
                valid_cells_geom = getattr(table_obj, "cells", [])
                total_grid_cells = sum(len(row) for row in raw_grid if isinstance(row, (list, tuple)))
                
                can_map_1_to_1 = isinstance(valid_cells_geom, list) and len(valid_cells_geom) == total_grid_cells
                if can_map_1_to_1:
                    geom_status = "available"
                else:
                    warnings.append({"page_number": page_num, "component": "table_geometry", "warning": "Geometry length mismatch. Bboxes set to null to protect text integrity."})

                geom_idx = 0
                for r_idx, row in enumerate(raw_grid):
                    if not isinstance(row, (list, tuple)): 
                        row = [str(row)] 
                        
                    for c_idx, cell_text in enumerate(row):
                        cell_bbox, bbox_source = None, "unavailable"
                        
                        if can_map_1_to_1:
                            try:
                                c_geom = valid_cells_geom[geom_idx]
                                parsed_bbox = self._bbox(c_geom)
                                if parsed_bbox:
                                    cell_bbox = parsed_bbox
                                    bbox_source = "pdfplumber"
                            except Exception:
                                geom_status = "partial"
                            geom_idx += 1

                        cells.append({
                            "row_idx": r_idx, "col_idx": c_idx,
                            "row_span": 1, "col_span": 1, 
                            "bbox": cell_bbox, "bbox_source": bbox_source,
                            "text": str(cell_text).strip() if cell_text is not None else "",
                            "is_header": r_idx == 0, 
                            "is_merged": None # Explicitly declaring unproven rather than False
                        })
                
                tables_data.append({
                    "type": "table", "bbox": bbox, "page_number": page_num,
                    "extraction_method": "native_pdf", "cells": cells, "_page_height": page_h,
                    "col_count": len(raw_grid[0]) if isinstance(raw_grid[0], (list, tuple)) else 0,
                    "geometry_status": geom_status,
                    "merged_span_status": "unavailable",
                    "text_status": "available"
                })
        except Exception as e:
            warnings.append({"page_number": page_num, "component": "table_fatal", "error": f"Table block skipped: {str(e)}"})
            
        return tables_data, warnings

    ###########################################################################
    # 3. PAGE STRATEGY & ISOLATED OCR
    ###########################################################################

    def _evaluate_page_strategy(self, page: fitz.Page, blocks: List[Dict]) -> str:
        if not blocks: return "OCR_ONLY"
        
        text_chars = 0
        text_area = 0.0

        for b in blocks:
            if b.get("type") == 0:
                for l in b.get("lines", []):
                    for s in l.get("spans", []):
                        text_chars += len(s.get("text", ""))
                
                bbox = b.get("bbox")
                if bbox and len(bbox) == 4:
                    x0, y0, x1, y1 = bbox
                    if x1 > x0 and y1 > y0:
                        text_area += (x1 - x0) * (y1 - y0)

        page_area = page.rect.width * page.rect.height
        text_coverage = text_area / page_area if page_area > 0 else 0.0

        img_area = sum((r.x1-r.x0)*(r.y1-r.y0) for img in page.get_images() for r in page.get_image_rects(img[0]))
        img_coverage = img_area / page_area if page_area > 0 else 0.0

        if text_chars < 50 and img_coverage > 0.10: return "OCR_ONLY"
        if text_coverage < 0.005 or img_coverage > 0.30: return "HYBRID"
        return "NATIVE_ONLY"

    def _ocr_extract_safely(self, page: fitz.Page, native_bboxes: List[List[float]] = None, native_texts: List[str] = None) -> Tuple[List[Dict], str, str]:
        """Returns (ocr_elements, status_enum, error_message). Status: success|unavailable|failed"""
        if not self.ocr_available:
            return [], "unavailable", "Tesseract executable or python package missing."
            
        try:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            data = pytesseract.image_to_data(img, config=self.tesseract_config, output_type=Output.DICT)
            
            blocks, scale = {}, 72.0 / 300.0
            for i in range(len(data['text'])):
                word = data['text'][i].strip()
                try: conf = float(data['conf'][i])
                except (ValueError, TypeError): continue
                
                if conf > 30 and word:
                    b_id = f"{data['block_num'][i]}_{data['par_num'][i]}_{data['line_num'][i]}"
                    if b_id not in blocks:
                        blocks[b_id] = {"text": [], "conf": [], "x0": data['left'][i], "y0": data['top'][i], "x1": data['left'][i]+data['width'][i], "y1": data['top'][i]+data['height'][i]}
                    else:
                        b = blocks[b_id]
                        b["x0"], b["y0"] = min(b["x0"], data['left'][i]), min(b["y0"], data['top'][i])
                        b["x1"], b["y1"] = max(b["x1"], data['left'][i]+data['width'][i]), max(b["y1"], data['top'][i]+data['height'][i])
                    blocks[b_id]["text"].append(word)
                    blocks[b_id]["conf"].append(conf)

            ocr_elements = []
            for b in blocks.values():
                bbox = self._bbox([b["x0"]*scale, b["y0"]*scale, b["x1"]*scale, b["y1"]*scale])
                text = " ".join(b["text"])
                
                is_duplicate = False
                if native_bboxes and native_texts:
                    for n_idx, n_box in enumerate(native_bboxes):
                        if self._calculate_overlap_ratio(bbox, n_box) > 0.5:
                            if self._token_similarity(text, native_texts[n_idx]) > 0.6:
                                is_duplicate = True
                                break
                
                if not is_duplicate:
                    ocr_elements.append({
                        "type": "raw_text", "text": text,
                        "extraction_method": "ocr", "extraction_confidence": round(statistics.mean(b["conf"])/100.0, 2),
                        "ocr_status": "success",
                        "bbox": bbox, "font_size": None, 
                        "estimated_font_size": round(bbox[3] - bbox[1], 1) if bbox else 12.0, 
                        "font_source": "ocr_estimate"
                    })
            return ocr_elements, "success", ""
        except Exception as e:
            logger.error(f"OCR extraction exception: {str(e)}")
            return [], "failed", str(e)

    ###########################################################################
    # 4. SPATIAL LAYOUT & READING ORDER
    ###########################################################################

    def _sort_reading_order(self, elements: List[Dict], page_width: float) -> List[Dict]:
        if not elements: return []
        full_width, others = [], []
        for el in elements:
            if el.get("bbox") and (el["bbox"][2] - el["bbox"][0]) > page_width * 0.70: 
                full_width.append(el)
            else: 
                others.append(el)
            
        full_width.sort(key=lambda e: e["bbox"][1] if e.get("bbox") else 0)
        final_order, current_y = [], 0.0
        
        for fw in full_width:
            band_elements = [e for e in others if e.get("bbox") and e["bbox"][1] >= current_y and e["bbox"][3] <= fw["bbox"][1] + 15]
            final_order.extend(self._sort_band_columns(band_elements))
            final_order.append(fw)
            current_y = fw["bbox"][3]
            
        remaining = [e for e in others if e.get("bbox") and e["bbox"][1] >= current_y]
        final_order.extend(self._sort_band_columns(remaining))
        final_order.extend([e for e in others if not e.get("bbox")])
        return final_order

    def _sort_band_columns(self, band_elements: List[Dict]) -> List[Dict]:
        if not band_elements: return []
        left_edges = sorted([e["bbox"][0] for e in band_elements if e.get("bbox")])
        if not left_edges: return band_elements
        
        column_bounds = []
        for x0 in left_edges:
            if not column_bounds or (x0 - column_bounds[-1]["x0"]) > 60:
                column_bounds.append({"x0": x0, "elements": []})

        for el in band_elements:
            if not el.get("bbox"): continue
            best_col, min_dist = column_bounds[0], float('inf')
            cx = (el["bbox"][0] + el["bbox"][2]) / 2
            for col in column_bounds:
                dist = abs(cx - col["x0"]) 
                if dist < min_dist: min_dist, best_col = dist, col
            best_col["elements"].append(el)

        band_order = []
        for col in column_bounds:
            band_order.extend(sorted(col["elements"], key=lambda e: e["bbox"][1]))
        return band_order

    ###########################################################################
    # 5. MASTER EXTRACTION PIPELINE
    ###########################################################################

    async def build_structural_tree(self, document_id: str) -> Dict[str, Any]:
        pdf_path = self._locate_pdf(document_id)
        folders = self._setup_directories(document_id)
        pdf_hash = self._hash_content(pdf_path.read_bytes())
        
        raw_elements, image_assets = [], {}
        page_metrics, page_warnings, page_failures = [], [], []
        toc_entries = []

        stats = {
            "total_pages": 0, "pages_processed": 0, "pages_with_native_text": 0,
            "pages_ocr_attempted": 0, "pages_ocr_success": 0, "pages_ocr_unavailable": 0,
            "pages_ocr_failed": 0, "pages_with_ocr_content": 0,
            "pages_with_warnings": 0, "pages_failed": 0, "tables_extracted": 0, 
            "unique_image_assets_extracted": 0, "image_occurrences_extracted": 0
        }

        with fitz.open(str(pdf_path)) as doc_fitz, pdfplumber.open(str(pdf_path)) as doc_plumber:
            stats["total_pages"] = len(doc_fitz)
            table_of_contents = [{"level": i[0], "title": i[1].strip(), "page_number": i[2]} for i in doc_fitz.get_toc()]
            toc_entries = [t["title"].lower() for t in table_of_contents if t.get("title")]
            
            for page_idx in range(stats["total_pages"]):
                page_num = page_idx + 1
                t_start = time.time()
                page_has_warning = False
                
                try:
                    page_fitz = doc_fitz[page_idx]
                    page_plumber = doc_plumber.pages[page_idx]
                    page_h, page_w = page_fitz.rect.height, page_fitz.rect.width
                except Exception as e:
                    page_failures.append({"page_number": page_num, "error": f"Fatal page load failure: {str(e)}"})
                    stats["pages_failed"] += 1
                    continue
                
                page_raw, native_bboxes, native_texts = [], [], []

                # 1. STRATEGY EVALUATION (Fault Isolated)
                try:
                    blocks = page_fitz.get_text("dict").get("blocks", [])
                    strategy = self._evaluate_page_strategy(page_fitz, blocks)
                except Exception as e:
                    page_warnings.append({"page_number": page_num, "component": "strategy", "warning": f"Eval failed: {str(e)}"})
                    strategy, blocks = "NATIVE_ONLY", []
                    page_has_warning = True

                # 2. TABLES (Fault Isolated)
                tables_data, tbl_warnings = self._extract_tables_safely(page_plumber, page_num, page_h)
                if tbl_warnings: 
                    page_warnings.extend(tbl_warnings)
                    page_has_warning = True
                page_raw.extend(tables_data)
                stats["tables_extracted"] += len(tables_data)

                # 3. IMAGES (Fault Isolated)
                try:
                    for img_info in page_fitz.get_images(full=True):
                        xref = img_info[0]
                        base_img = doc_fitz.extract_image(xref)
                        img_hash = self._hash_content(base_img["image"])[:16]
                        asset_id = f"asset_{document_id}_{img_hash}"
                        
                        if asset_id not in image_assets:
                            img_path = f"{asset_id}.{base_img['ext']}"
                            with open(folders["assets"] / img_path, "wb") as f: f.write(base_img["image"])
                            image_assets[asset_id] = {
                                "asset_id": asset_id, "xref_original": xref, "hash": img_hash,
                                "width": base_img["width"], "height": base_img["height"], 
                                "ext": base_img["ext"], "path": f"assets/{img_path}", "occurrence_count": 0
                            }
                            stats["unique_image_assets_extracted"] += 1
                        
                        image_assets[asset_id]["occurrence_count"] += 1
                        stats["image_occurrences_extracted"] += 1
                        for rect in page_fitz.get_image_rects(xref):
                            page_raw.append({
                                "type": "image_occurrence", "asset_id": asset_id,
                                "bbox": self._bbox([rect.x0, rect.y0, rect.x1, rect.y1]),
                                "page_number": page_num, "extraction_method": "native_pdf", "_page_height": page_h
                            })
                except Exception as e:
                    page_warnings.append({"page_number": page_num, "component": "image", "warning": str(e)})
                    page_has_warning = True

                # 4. NATIVE TEXT (Fault Isolated)
                native_extracted = False
                if strategy in ["NATIVE_ONLY", "HYBRID"]:
                    try:
                        for block in blocks:
                            if block.get("type") != 0: continue
                            bbox = self._bbox(block["bbox"])
                            text, max_font, is_bold, font_name = "", 0.0, False, ""
                            for l in block.get("lines", []):
                                for s in l.get("spans", []):
                                    text += s.get("text", "")
                                    max_font = max(max_font, s.get("size", 0))
                                    font_name = s.get("font", "")
                                    if (s.get("flags", 0) & 2) or "bold" in font_name.lower(): is_bold = True
                                text += " "
                            
                            text = text.strip()
                            if text:
                                native_bboxes.append(bbox)
                                native_texts.append(text)
                                native_extracted = True
                                page_raw.append({
                                    "type": "raw_text", "text": text, "font_size": round(max_font, 1),
                                    "font_family": font_name, "font_source": "native_pdf",
                                    "is_bold": is_bold, "bbox": bbox, "page_number": page_num,
                                    "extraction_method": "native_pdf", "_page_height": page_h
                                })
                        if native_extracted: stats["pages_with_native_text"] += 1
                    except Exception as e:
                        page_warnings.append({"page_number": page_num, "component": "native_text", "warning": str(e)})
                        page_has_warning = True

                # 5. OCR (Strictly Isolated & Explicit Enum State)
                if strategy in ["OCR_ONLY", "HYBRID"]:
                    stats["pages_ocr_attempted"] += 1
                    args = (page_fitz,) if strategy == "OCR_ONLY" else (page_fitz, native_bboxes, native_texts)
                    
                    ocr_blocks, ocr_status, ocr_err = self._ocr_extract_safely(*args)
                    
                    if ocr_status == "success":
                        stats["pages_ocr_success"] += 1
                        if ocr_blocks:
                            stats["pages_with_ocr_content"] += 1
                            for b in ocr_blocks:
                                b["page_number"] = page_num
                                b["_page_height"] = page_h
                            page_raw.extend(ocr_blocks)
                    elif ocr_status == "unavailable":
                        stats["pages_ocr_unavailable"] += 1
                        page_warnings.append({"page_number": page_num, "component": "ocr", "warning": "Tesseract unavailable"})
                        page_has_warning = True
                    elif ocr_status == "failed":
                        stats["pages_ocr_failed"] += 1
                        page_warnings.append({"page_number": page_num, "component": "ocr", "warning": f"OCR failed: {ocr_err}"})
                        page_has_warning = True
                        
                    # Scanned Degradation State (Recorded to page_raw without polluting other elements)
                    if strategy == "OCR_ONLY" and ocr_status != "success":
                        page_raw.append({
                            "type": "scanned_page", "bbox": [0.0, 0.0, page_w, page_h],
                            "page_number": page_num, "text": "", "ocr_status": ocr_status,
                            "extraction_method": "unavailable", "_page_height": page_h
                        })

                try:
                    sorted_page = self._sort_reading_order(page_raw, page_w)
                    raw_elements.extend(sorted_page)
                except Exception as e:
                    page_warnings.append({"page_number": page_num, "component": "layout_sort", "warning": str(e)})
                    raw_elements.extend(page_raw) 
                    page_has_warning = True

                if page_has_warning: stats["pages_with_warnings"] += 1
                stats["pages_processed"] += 1
                page_metrics.append({"page": page_num, "strategy": strategy, "duration_sec": round(time.time() - t_start, 2)})

        # --- PRE-PERSISTENCE: MARK FURNITURE & ASSIGN IDS ---
        margins = []
        for el in raw_elements:
            if el.get("type") == "raw_text" and el.get("bbox"):
                y0, y1 = el["bbox"][1], el["bbox"][3]
                page_h = el.get("_page_height", 800)
                if y1 < page_h * 0.08 or y0 > page_h * 0.92:
                    margins.append(re.sub(r'\d+', '#', el["text"].strip().lower()))
                    
        freq, threshold = Counter(margins), max(3, int(stats["total_pages"] * 0.05))
        for el in raw_elements:
            el["is_furniture"] = False
            if el.get("type") == "raw_text" and el.get("bbox"):
                y0, y1 = el["bbox"][1], el["bbox"][3]
                if y1 < el.get("_page_height", 800) * 0.08 or y0 > el.get("_page_height", 800) * 0.92:
                    if freq[re.sub(r'\d+', '#', el["text"].strip().lower())] > threshold:
                        el["is_furniture"] = True

        doc_seq = 1
        current_page, page_seq = -1, 1
        for el in raw_elements:
            if el["page_number"] != current_page:
                current_page, page_seq = el["page_number"], 1
            el_type_short = el['type'].split('_')[0]
            el["element_id"] = f"{document_id}_p{current_page}_s{page_seq}_{el_type_short}"
            el["provenance_id"] = self._generate_provenance_id(pdf_hash, current_page, el.get("bbox"), el["type"], el.get("text", ""), doc_seq)
            el["document_sequence"] = doc_seq
            el["page_sequence"] = page_seq
            doc_seq += 1
            page_seq += 1

        with open(folders["root"] / "raw_elements.jsonl", "w") as f:
            for el in raw_elements: f.write(json.dumps({k:v for k,v in el.items() if not k.startswith("_")}) + "\n")

        # --- PHASE 2: NORMALIZATION (Deep Copy) ---
        normalized_elements = [copy.deepcopy(el) for el in raw_elements if not el.get("is_furniture")]
        base_fonts = [e.get("font_size") for e in normalized_elements if e.get("type") == "raw_text" and e.get("font_size")]
        median_font = statistics.median(base_fonts) if base_fonts else 12.0
        
        for el in normalized_elements:
            if el["type"] == "raw_text":
                text = el["text"]
                fs = el.get("font_size") or el.get("estimated_font_size", 12.0)
                is_bold = el.get("is_bold", False)
                has_num = bool(re.match(r'^((Chapter|Section)\s+[IVX\d]+|\d+(\.\d+)+)\b', text, re.IGNORECASE))
                
                h_level, h_conf = 0, 1.0
                if 0 < len(text.split()) <= 15:
                    toc_match = any(self._token_similarity(text.lower(), toc) > 0.8 for toc in toc_entries)
                    if toc_match and (fs > median_font + 1.0 or is_bold or has_num):
                        h_level, h_conf = 2, 0.95 
                        if fs > median_font + 2.0: h_level = 1
                    elif fs > median_font + 3.0:
                        h_level, h_conf = 1, 0.90
                    elif (fs > median_font + 1.0) or (is_bold and has_num):
                        h_level, h_conf = 2, 0.85
                        
                if h_level > 0:
                    el["type"] = "heading"
                    el["heading_level"] = h_level
                    el["classification_confidence"] = h_conf
                elif re.match(r"^(fig\.?|figure|table|chart)\s*\d+", text, re.IGNORECASE):
                    el["type"] = "caption"
                    el["classification_confidence"] = 0.90
                else:
                    el["type"] = "paragraph"

        # --- PHASE 3: GRAPH EDGES ---
        graph_nodes, active_path, table_group_counter = [], [], 1
        page_targets = {}
        for el in normalized_elements:
            if el["type"] in ["table", "image_occurrence"]:
                page_targets.setdefault(el["page_number"], []).append(el)

        for i, el in enumerate(normalized_elements):
            el["previous_element_id"] = normalized_elements[i-1]["element_id"] if i > 0 else None
            el["next_element_id"] = normalized_elements[i+1]["element_id"] if i < len(normalized_elements)-1 else None
            el["parent_section_id"], el["caption_element_id"], el["target_element_id"] = None, None, None
            el["continues_from_element_id"], el["continues_to_element_id"] = None, None

            if el["type"] == "heading":
                level = el["heading_level"]
                while active_path and active_path[-1]["level"] >= level: active_path.pop()
                active_path.append({"element_id": el["element_id"], "level": level, "text": el["text"]})
            
            if active_path:
                el["parent_section_id"] = active_path[-1]["element_id"]
                el["context"] = {
                    "source": "heading_inheritance",
                    "path": [dict(p) for p in active_path],
                    "path_element_ids": [p["element_id"] for p in active_path]
                }

            if el["type"] == "table" and i > 0:
                prev = normalized_elements[i-1]
                if prev["type"] == "table" and el["page_number"] - prev["page_number"] <= 1:
                    if prev.get("col_count") == el.get("col_count") and prev.get("bbox") and el.get("bbox"):
                        if abs(prev["bbox"][0] - el["bbox"][0]) < 20 and abs(prev["bbox"][2] - el["bbox"][2]) < 20:
                            grp = prev.get("table_group_id", f"tblgrp_{document_id}_{table_group_counter}")
                            table_group_counter += 1
                            prev["table_group_id"], el["table_group_id"] = grp, grp
                            prev["continues_to_element_id"] = el["element_id"]
                            el["continues_from_element_id"] = prev["element_id"]

            if el["type"] == "caption" and el.get("bbox"):
                best_dist, best_target = float('inf'), None
                for target in page_targets.get(el["page_number"], []):
                    if not target.get("bbox"): continue
                    cap_center = (el["bbox"][0] + el["bbox"][2]) / 2
                    tar_center = (target["bbox"][0] + target["bbox"][2]) / 2
                    if abs(cap_center - tar_center) < 150: 
                        dy = min(abs(el["bbox"][1] - target["bbox"][3]), abs(target["bbox"][1] - el["bbox"][3]))
                        if dy < best_dist and dy < 150: 
                            best_dist, best_target = dy, target
                if best_target:
                    el["target_element_id"] = best_target["element_id"]
                    best_target["caption_element_id"] = el["element_id"]

            graph_nodes.append({
                "element_id": el["element_id"], "provenance_id": el["provenance_id"],
                "parent_section_id": el.get("parent_section_id"), "previous_element_id": el.get("previous_element_id"),
                "next_element_id": el.get("next_element_id"), "caption_element_id": el.get("caption_element_id"),
                "target_element_id": el.get("target_element_id"), "continues_from_element_id": el.get("continues_from_element_id"),
                "continues_to_element_id": el.get("continues_to_element_id")
            })

        # --- PHASE 4: PERSISTENCE & COMPLIANT API RETURN ---
        manifest = {
            "document_id": document_id, "schema_version": self.schema_version,
            "extraction_version": self.extraction_version, "source_pdf_hash": pdf_hash,
            "ocr_health": {
                "provider": "tesseract", "python_package_available": PYTESSERACT_AVAILABLE,
                "executable_available": self.tesseract_exe_found, "available": self.ocr_available,
                "reason": "tesseract_executable_not_found" if not self.tesseract_exe_found else "ok"
            },
            "extraction_summary": stats,
            "page_failures": page_failures, "page_warnings": page_warnings,
            "page_metrics": page_metrics
        }

        with open(folders["root"] / "manifest.json", "w") as f: json.dump(manifest, f, indent=2)
        with open(folders["root"] / "assets_manifest.json", "w") as f: json.dump(list(image_assets.values()), f, indent=2)
        with open(folders["root"] / "normalized_elements.jsonl", "w") as f:
            for el in normalized_elements: f.write(json.dumps({k:v for k,v in el.items() if not k.startswith("_")}) + "\n")
        with open(folders["root"] / "structural_graph.json", "w") as f: json.dump(graph_nodes, f, indent=2)

        summary = {
            "success": True, "message": "Structure extraction complete.",
            "data": {
                "manifest": manifest,
                "data_locations": {
                    "raw": f"/storage/processed/{document_id}/raw_elements.jsonl",
                    "normalized": f"/storage/processed/{document_id}/normalized_elements.jsonl",
                    "graph": f"/storage/processed/{document_id}/structural_graph.json",
                    "assets": f"/storage/processed/{document_id}/assets_manifest.json"
                }
            }
        }
        logger.info(f"Structure extraction and provenance established for {document_id}")
        return summary





# import io
# import json
# import re
# import math
# from collections import Counter
# from pathlib import Path
# from typing import Any, Dict, List, Tuple

# import pymupdf as fitz  # Enterprise-standard alias for PyMuPDF
# import pdfplumber

# from app.core.config import settings
# from app.core.exceptions import DocumentNotFoundError, ProcessingError
# from app.core.logger import logger


# class StructureService:
#     def __init__(self):
#         self.raw_dir = settings.STORAGE_RAW_DIR
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR

#         # Semantic patterns for rich extraction
#         self.patterns = {
#             "isbn": re.compile(r"(?:ISBN(?:-1[03])?:?\s*)?(?=[-0-9 ]{13,17})(?:97[89][-\s]?)?[0-9]{1,5}[-\s]?[0-9]+[-\s]?[0-9]+[-\s]?[0-9X]", re.IGNORECASE),
#             "doi": re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b", re.IGNORECASE),
#             "copyright": re.compile(r"(©|Copyright)\s*(?:\d{4})", re.IGNORECASE),
#             "edition": re.compile(r"(\b(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|\d+(st|nd|rd|th))\b\s+Edition)", re.IGNORECASE),
#             "url": re.compile(r"(https?://[^\s]+|www\.[^\s]+)", re.IGNORECASE),
#             "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
#             "caption": re.compile(r"^(fig\.?|figure|table|chart|plate|scheme|map)\s*\d+", re.IGNORECASE),
#             "list_item": re.compile(r"^(\d+[\.\)]|[a-zA-Z][\.\)]|[•\-\*])\s+"),
#             "cross_ref": re.compile(r"\b(see|refer to)\s+(figure|fig\.|table|chapter|section|appendix)\s+\d+", re.IGNORECASE),
#             "equation": re.compile(r"(=|≈|≠|∑|∫|√|Δ|Ω|±|≤|≥)")
#         }

#     ###########################################################################
#     # STAGE 0: I/O HELPERS
#     ###########################################################################

#     def _locate_pdf(self, document_id: str) -> Path:
#         paths_to_check = [
#             self.raw_dir / document_id / "original.pdf",
#             self.raw_dir / f"{document_id}.pdf"
#         ]
#         for p in paths_to_check:
#             if p.exists(): return p
#         processed = self.processed_dir / document_id
#         if processed.exists() and list(processed.glob("*.pdf")):
#             return list(processed.glob("*.pdf"))[0]
#         raise DocumentNotFoundError(document_id)

#     def _create_output_directories(self, document_id: str) -> Dict[str, Path]:
#         root = self.processed_dir / document_id
#         folders = {"root": root, "images": root / "images", "tables": root / "tables"}
#         for f in folders.values(): f.mkdir(parents=True, exist_ok=True)
#         return folders

#     def _bbox(self, bbox) -> List[float]:
#         return [round(float(x), 2) for x in bbox]

#     def _inside_table(self, bbox: List[float], table_boxes: List[List[float]]) -> bool:
#         x0, y0, x1, y1 = bbox
#         for tx0, ty0, tx1, ty1 in table_boxes:
#             if x0 >= tx0 - 2 and x1 <= tx1 + 2 and y0 >= ty0 - 2 and y1 <= ty1 + 2:
#                 return True
#         return False

#     def _save_image(self, image_bytes: bytes, image_path: Path):
#         with open(image_path, "wb") as f: f.write(image_bytes)

#     ###########################################################################
#     # STAGE 1: DOCUMENT PROFILING (TYPOGRAPHY & NOISE REMOVAL)
#     ###########################################################################

#     def _profile_document(self, doc_fitz: fitz.Document) -> Dict[str, Any]:
#         """Calculates dominant fonts and identifies repeating headers/footers."""
#         font_sizes = []
#         top_texts, bottom_texts = [], []
        
#         for page_idx in range(min(len(doc_fitz), 50)):  # Sample up to 50 pages
#             page = doc_fitz[page_idx]
#             rect = page.rect
#             blocks = page.get_text("dict").get("blocks", [])
            
#             for b in blocks:
#                 if b.get("type") != 0: continue
#                 bbox = b["bbox"]
#                 text = "".join([s["text"] for l in b["lines"] for s in l["spans"]]).strip()
#                 if not text: continue
                
#                 # Collect font sizes
#                 for l in b["lines"]:
#                     for s in l["spans"]:
#                         font_sizes.append(round(s["size"]))
                        
#                 # Collect margin texts for header/footer detection
#                 if bbox[1] < rect.height * 0.08: top_texts.append(text)
#                 if bbox[3] > rect.height * 0.92: bottom_texts.append(text)

#         if not font_sizes:
#             return {"dominant_font": 12.0, "headers": set(), "footers": set()}

#         dominant_font = Counter(font_sizes).most_common(1)[0][0]
        
#         # If a text appears in the margins on more than 3 pages, it's a running header/footer
#         top_repeats = {t for t, count in Counter(top_texts).items() if count > 3}
#         bottom_repeats = {t for t, count in Counter(bottom_texts).items() if count > 3}

#         return {
#             "dominant_font": dominant_font,
#             "headers": top_repeats,
#             "footers": bottom_repeats
#         }

#     ###########################################################################
#     # STAGE 2: SEMANTIC CLASSIFICATION
#     ###########################################################################

#     def _classify_page(self, page_num: int, full_text: str) -> str:
#         text_lower = full_text.lower()
#         if page_num == 1: return "cover"
#         if "isbn" in text_lower and page_num < 10: return "copyright"
#         if ("contents" in text_lower or "table of contents" in text_lower) and page_num < 25: return "toc"
#         if ("preface" in text_lower or "foreword" in text_lower) and page_num < 30: return "preface"
#         if ("bibliography" in text_lower[:200] or "references" in text_lower[:200]) and page_num > 10: return "references"
#         if ("appendix" in text_lower[:200] or "annex" in text_lower[:200]) and page_num > 10: return "appendix"
#         if page_num < 10: return "title"
#         return "body"

#     def _classify_element(self, text: str, font_size: float, is_bold: bool, profile: Dict) -> Tuple[str, int, float]:
#         """
#         Dynamically classifies text based on document typography profile and regex.
#         Returns: (type, heading_level, confidence)
#         """
#         text_clean = text.strip()
#         dom_font = profile["dominant_font"]

#         # 1. Regex Rules (High Confidence)
#         if self.patterns["isbn"].search(text_clean): return ("isbn", 0, 0.99)
#         if self.patterns["doi"].search(text_clean): return ("doi", 0, 0.99)
#         if self.patterns["caption"].match(text_clean): return ("caption", 0, 0.95)
#         if self.patterns["list_item"].match(text_clean): return ("list_item", 0, 0.90)
        
#         # Determine Equation likelihood
#         if self.patterns["equation"].search(text_clean) and len(text_clean) < 100:
#             return ("equation", 0, 0.85)

#         # 2. Dynamic Typography Hierarchy
#         # Compare current font to the dominant body font of the whole book
#         word_count = len(text_clean.split())
#         is_short = word_count < 20
#         ends_with_punctuation = re.search(r'[.?!:]$', text_clean)

#         if is_short and not ends_with_punctuation:
#             if font_size > dom_font * 1.5: return ("heading", 1, 0.95) # Chapter
#             if font_size > dom_font * 1.2: return ("heading", 2, 0.92) # Section
#             if font_size > dom_font and is_bold: return ("heading", 3, 0.88) # Subsection
#             if font_size == dom_font and is_bold: return ("heading", 4, 0.80) # Minor heading

#         return ("paragraph", 0, 0.90)

#     ###########################################################################
#     # STAGE 3: SPATIAL LINKING
#     ###########################################################################

#     def _link_captions_spatially(self, elements: List[Dict]):
#         """Links captions to the closest image or table using Euclidean geometry."""
#         captions = [e for e in elements if e["type"] == "caption"]
#         targets = [e for e in elements if e["type"] in ["image", "table"]]

#         for cap in captions:
#             cx, cy = cap["bbox"][0], cap["bbox"][1]
#             best_target = None
#             min_dist = float('inf')

#             for t in targets:
#                 # Calculate center of target bounding box
#                 tx = (t["bbox"][0] + t["bbox"][2]) / 2
#                 ty = (t["bbox"][1] + t["bbox"][3]) / 2
#                 dist = math.hypot(cx - tx, cy - ty)

#                 # Link if within a reasonable spatial radius (e.g., 200 pts)
#                 if dist < min_dist and dist < 200:
#                     min_dist = dist
#                     best_target = t
            
#             if best_target:
#                 cap["target_element_id"] = best_target["element_id"]
#                 best_target["caption_element_id"] = cap["element_id"]

#     ###########################################################################
#     # STAGE 4: GRAPH & CHUNK BOUNDARY BUILDER
#     ###########################################################################

#     def _build_knowledge_graph(self, elements: List[Dict]) -> Dict[str, Any]:
#         """
#         Builds parent/child trees and assigns semantic_chunk_ids for RAG.
#         """
#         document_graph = {"type": "document", "id": "root", "children": []}
#         stack = [{"level": 0, "node": document_graph, "id": "root", "path": []}]
        
#         current_chunk_id = "chunk_front_matter"

#         for i, el in enumerate(elements):
#             el["previous_id"] = elements[i-1]["element_id"] if i > 0 else None
#             el["next_id"] = elements[i+1]["element_id"] if i < len(elements)-1 else None

#             h_level = el.get("heading_level", 0)
            
#             if el["type"] == "heading":
#                 while len(stack) > 1 and stack[-1]["level"] >= h_level:
#                     stack.pop()
                    
#                 parent = stack[-1]
#                 el["parent_id"] = parent["id"]
#                 current_chunk_id = f"chunk_{el['element_id']}"  # New chunk starts at heading
                
#                 new_node = {
#                     "id": el["element_id"],
#                     "type": "heading",
#                     "text": el["text"],
#                     "level": h_level,
#                     "children": []
#                 }
#                 parent["node"]["children"].append(new_node)
                
#                 new_path = parent["path"] + [el["text"]]
#                 stack.append({"level": h_level, "node": new_node, "id": el["element_id"], "path": new_path})
#                 el["section_path"] = new_path
                
#             else:
#                 parent = stack[-1]
#                 el["parent_id"] = parent["id"]
#                 el["section_path"] = parent["path"]
#                 parent["node"]["children"].append({
#                     "id": el["element_id"],
#                     "type": el["type"]
#                 })

#             # Assign RAG Chunk ID
#             el["semantic_chunk_id"] = current_chunk_id

#             # Cross-reference tagging
#             cross_refs = self.patterns["cross_ref"].findall(el.get("text", ""))
#             if cross_refs:
#                 el["contains_cross_references"] = [" ".join(ref) for ref in cross_refs]

#         return document_graph

#     ###########################################################################
#     # MASTER ORCHESTRATOR
#     ###########################################################################

#     async def build_structural_tree(self, document_id: str) -> Dict[str, Any]:
#         pdf_path = self._locate_pdf(document_id)
#         folders = self._create_output_directories(document_id)

#         try:
#             logger.info(f"Extracting Enterprise-grade Document Intelligence for {document_id}")
#             doc_fitz = fitz.open(str(pdf_path))
#             total_pages = len(doc_fitz)

#             # Stage 1: Profile Typography & Noise
#             doc_profile = self._profile_document(doc_fitz)

#             toc_raw = doc_fitz.get_toc()
#             table_of_contents = [{"level": i[0], "title": i[1].strip(), "page_number": i[2]} for i in toc_raw]

#             global_elements = []  
#             pages_data = []       
#             seq_idx = 1

#             with pdfplumber.open(str(pdf_path)) as doc_plumber:
#                 for page_idx in range(total_pages):
#                     page_num = page_idx + 1
#                     page_fitz = doc_fitz[page_idx]
#                     page_plumber = doc_plumber.pages[page_idx]
#                     rect = page_fitz.rect

#                     full_page_text = chr(12).join([b[4] for b in page_fitz.get_text("blocks")])
#                     page_type = self._classify_page(page_num, full_page_text)

#                     raw_page_elements = []
#                     table_bboxes = []

#                     # 1. TABLES
#                     for t_idx, table_obj in enumerate(page_plumber.find_tables()):
#                         bbox = self._bbox(table_obj.bbox)
#                         table_data = table_obj.extract()
#                         table_bboxes.append(bbox)
#                         raw_page_elements.append({
#                             "element_id": f"{document_id}_p{page_num}_table_{t_idx + 1}",
#                             "type": "table",
#                             "table_index": t_idx + 1,
#                             "bbox": bbox,
#                             "row_count": len(table_data),
#                             "col_count": len(table_data[0]) if table_data else 0,
#                             "rows": table_data,
#                             "confidence": 0.98
#                         })

#                     # 2. IMAGES
#                     for img_idx, img_info in enumerate(page_fitz.get_images(full=True)):
#                         xref = img_info[0]
#                         rects = page_fitz.get_image_rects(xref)
#                         base_image = doc_fitz.extract_image(xref)
#                         image_ext = base_image["ext"]
#                         image_filename = f"page_{page_num}_img_{img_idx + 1}.{image_ext}"
#                         self._save_image(base_image["image"], folders["images"] / image_filename)

#                         for img_rect in rects:
#                             img_area = img_rect.width * img_rect.height
#                             img_type = "figure"
#                             if page_type == "cover": img_type = "cover_image"
#                             elif page_type in ["title", "copyright"] and img_area < 5000: img_type = "logo"

#                             raw_page_elements.append({
#                                 "element_id": f"{document_id}_p{page_num}_img_{img_idx + 1}",
#                                 "type": img_type,
#                                 "image_index": img_idx + 1,
#                                 "xref": xref,
#                                 "bbox": self._bbox([img_rect.x0, img_rect.y0, img_rect.x1, img_rect.y1]),
#                                 "image_path": f"/storage/processed/{document_id}/images/{image_filename}",
#                                 "width": round(img_rect.width, 2),
#                                 "height": round(img_rect.height, 2),
#                                 "confidence": 0.99
#                             })

#                     # 3. TEXT & TYPOGRAPHY
#                     blocks = page_fitz.get_text("dict").get("blocks", [])
#                     if not blocks:
#                         raw_page_elements.append({
#                             "element_id": f"{document_id}_p{page_num}_scanned_{seq_idx}",
#                             "type": "scanned_page",
#                             "text": "",
#                             "bbox": self._bbox([0, 0, rect.width, rect.height]),
#                             "requires_ocr": True,
#                             "confidence": 1.0
#                         })
#                     else:
#                         for block in blocks:
#                             if block.get("type") != 0: continue
#                             block_bbox = self._bbox(block["bbox"])
                            
#                             # Filter Tables and Noise
#                             if self._inside_table(block_bbox, table_bboxes): continue
                            
#                             block_text, max_font, is_bold = "", 0.0, False
#                             for line in block.get("lines", []):
#                                 for span in line.get("spans", []):
#                                     block_text += span.get("text", "")
#                                     if span.get("size", 0) > max_font: max_font = span.get("size", 0)
#                                     if (span.get("flags", 0) & 2) or "bold" in span.get("font", "").lower():
#                                         is_bold = True
#                                 block_text += " "

#                             block_text = block_text.strip()
#                             if not block_text: continue

#                             # Header/Footer Removal
#                             if block_bbox[1] < rect.height * 0.08 and block_text in doc_profile["headers"]:
#                                 raw_page_elements.append({"type": "header", "text": block_text, "bbox": block_bbox, "confidence": 0.95})
#                                 continue
#                             if block_bbox[3] > rect.height * 0.92 and block_text in doc_profile["footers"]:
#                                 raw_page_elements.append({"type": "footer", "text": block_text, "bbox": block_bbox, "confidence": 0.95})
#                                 continue

#                             # Page Numbers
#                             if (block_bbox[1] < rect.height * 0.1 or block_bbox[3] > rect.height * 0.9) and block_text.isdigit():
#                                 raw_page_elements.append({"type": "page_number", "text": block_text, "bbox": block_bbox, "confidence": 0.98})
#                                 continue

#                             # Semantic Classification
#                             el_type, h_level, conf = self._classify_element(block_text, max_font, is_bold, doc_profile)

#                             raw_page_elements.append({
#                                 "type": el_type,
#                                 "heading_level": h_level,
#                                 "text": block_text,
#                                 "font_size": round(max_font, 1),
#                                 "is_bold": is_bold,
#                                 "bbox": block_bbox,
#                                 "confidence": conf
#                             })

#                     # Page Sorting & ID generation
#                     sorted_page_elements = self._sort_reading_order([e for e in raw_page_elements if e["type"] not in ["header", "footer", "page_number"]])
                    
#                     for el in sorted_page_elements:
#                         if "element_id" not in el:
#                             el["element_id"] = f"{document_id}_p{page_num}_{el['type']}_{seq_idx}"
#                         el["page_number"] = page_num
#                         el["page_type"] = page_type
#                         el["reading_sequence"] = seq_idx
#                         global_elements.append(el)
#                         seq_idx += 1

#             doc_fitz.close()

#             # Stage 4: Spatial Linking
#             self._link_captions_spatially(global_elements)

#             # Stage 5: Semantic Graph & Chunks
#             document_graph = self._build_knowledge_graph(global_elements)

#             # Group pages for output
#             for page_num in range(1, total_pages + 1):
#                 page_elems = [e for e in global_elements if e.get("page_number") == page_num]
#                 if not page_elems: continue 
                
#                 pages_data.append({
#                     "page_number": page_num,
#                     "page_type": page_elems[0].get("page_type", "body"),
#                     "elements_count": len(page_elems),
#                     "elements": page_elems,
#                     "full_text": "\n\n".join([e.get("text", "") for e in page_elems if "text" in e])
#                 })

#             # Stage 6: Output Assembly
#             document_tree = {
#                 "document_id": document_id,
#                 "statistics": {
#                     "total_pages": total_pages,
#                     "elements_extracted": len(global_elements),
#                     "dominant_body_font": doc_profile["dominant_font"]
#                 },
#                 "has_native_toc": len(table_of_contents) > 0,
#                 "table_of_contents": table_of_contents,
#                 "document_graph": document_graph,
#                 "pages": pages_data
#             }

#             tree_path = folders["root"] / "document_tree.json"
#             with open(tree_path, "w", encoding="utf-8") as f:
#                 json.dump(document_tree, f, indent=4, ensure_ascii=False)

#             logger.info(f"Successfully compiled Semantic Document Intelligence for {document_id}")
#             return document_tree

#         except Exception as e:
#             logger.error(f"Error building intelligence tree for {document_id}: {str(e)}", exc_info=True)
#             raise ProcessingError(f"Failed to extract document structure: {str(e)}")






# import io
# import json
# import re
# import math
# from collections import Counter
# from pathlib import Path
# from typing import Any, Dict, List, Tuple

# import pymupdf as fitz  # Enterprise-standard alias for PyMuPDF
# import pdfplumber

# from app.core.config import settings
# from app.core.exceptions import DocumentNotFoundError, ProcessingError
# from app.core.logger import logger


# class StructureService:
#     def __init__(self):
#         self.raw_dir = settings.STORAGE_RAW_DIR
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR

#         # Semantic patterns for rich extraction
#         self.patterns = {
#             "isbn": re.compile(r"(?:ISBN(?:-1[03])?:?\s*)?(?=[-0-9 ]{13,17})(?:97[89][-\s]?)?[0-9]{1,5}[-\s]?[0-9]+[-\s]?[0-9]+[-\s]?[0-9X]", re.IGNORECASE),
#             "doi": re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b", re.IGNORECASE),
#             "copyright": re.compile(r"(©|Copyright)\s*(?:\d{4})", re.IGNORECASE),
#             "edition": re.compile(r"(\b(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|\d+(st|nd|rd|th))\b\s+Edition)", re.IGNORECASE),
#             "url": re.compile(r"(https?://[^\s]+|www\.[^\s]+)", re.IGNORECASE),
#             "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
#             "caption": re.compile(r"^(fig\.?|figure|table|chart|plate|scheme|map)\s*\d+", re.IGNORECASE),
#             "list_item": re.compile(r"^(\d+[\.\)]|[a-zA-Z][\.\)]|[•\-\*])\s+"),
#             "cross_ref": re.compile(r"\b(see|refer to)\s+(figure|fig\.|table|chapter|section|appendix)\s+\d+", re.IGNORECASE),
#             "equation": re.compile(r"(=|≈|≠|∑|∫|√|Δ|Ω|±|≤|≥)")
#         }

#     ###########################################################################
#     # STAGE 0: I/O HELPERS & SORTING
#     ###########################################################################

#     def _locate_pdf(self, document_id: str) -> Path:
#         paths_to_check = [
#             self.raw_dir / document_id / "original.pdf",
#             self.raw_dir / f"{document_id}.pdf"
#         ]
#         for p in paths_to_check:
#             if p.exists(): return p
#         processed = self.processed_dir / document_id
#         if processed.exists() and list(processed.glob("*.pdf")):
#             return list(processed.glob("*.pdf"))[0]
#         raise DocumentNotFoundError(document_id)

#     def _create_output_directories(self, document_id: str) -> Dict[str, Path]:
#         root = self.processed_dir / document_id
#         folders = {"root": root, "images": root / "images", "tables": root / "tables"}
#         for f in folders.values(): f.mkdir(parents=True, exist_ok=True)
#         return folders

#     def _bbox(self, bbox) -> List[float]:
#         return [round(float(x), 2) for x in bbox]

#     def _inside_table(self, bbox: List[float], table_boxes: List[List[float]]) -> bool:
#         x0, y0, x1, y1 = bbox
#         for tx0, ty0, tx1, ty1 in table_boxes:
#             if x0 >= tx0 - 2 and x1 <= tx1 + 2 and y0 >= ty0 - 2 and y1 <= ty1 + 2:
#                 return True
#         return False

#     def _save_image(self, image_bytes: bytes, image_path: Path):
#         with open(image_path, "wb") as f: f.write(image_bytes)

#     def _sort_reading_order(self, elements: List[Dict]) -> List[Dict]:
#         """Sorts elements top-to-bottom, left-to-right to support multi-column layouts."""
#         return sorted(
#             elements,
#             key=lambda x: (
#                 round(x["bbox"][1] / 10),  # Group roughly into 10px vertical bands
#                 round(x["bbox"][0])        # Then sort horizontally within the band
#             ),
#         )

#     ###########################################################################
#     # STAGE 1: DOCUMENT PROFILING (TYPOGRAPHY & NOISE REMOVAL)
#     ###########################################################################

#     def _profile_document(self, doc_fitz: fitz.Document) -> Dict[str, Any]:
#         """Calculates dominant fonts and identifies repeating headers/footers."""
#         font_sizes = []
#         top_texts, bottom_texts = [], []
        
#         for page_idx in range(min(len(doc_fitz), 50)):  # Sample up to 50 pages
#             page = doc_fitz[page_idx]
#             rect = page.rect
#             blocks = page.get_text("dict").get("blocks", [])
            
#             for b in blocks:
#                 if b.get("type") != 0: continue
#                 bbox = b["bbox"]
#                 text = "".join([s["text"] for l in b["lines"] for s in l["spans"]]).strip()
#                 if not text: continue
                
#                 # Collect font sizes
#                 for l in b["lines"]:
#                     for s in l["spans"]:
#                         font_sizes.append(round(s["size"]))
                        
#                 # Collect margin texts for header/footer detection
#                 if bbox[1] < rect.height * 0.08: top_texts.append(text)
#                 if bbox[3] > rect.height * 0.92: bottom_texts.append(text)

#         if not font_sizes:
#             return {"dominant_font": 12.0, "headers": set(), "footers": set()}

#         dominant_font = Counter(font_sizes).most_common(1)[0][0]
        
#         # If a text appears in the margins on more than 3 pages, it's a running header/footer
#         top_repeats = {t for t, count in Counter(top_texts).items() if count > 3}
#         bottom_repeats = {t for t, count in Counter(bottom_texts).items() if count > 3}

#         return {
#             "dominant_font": dominant_font,
#             "headers": top_repeats,
#             "footers": bottom_repeats
#         }

#     ###########################################################################
#     # STAGE 2: SEMANTIC CLASSIFICATION
#     ###########################################################################

#     def _classify_page(self, page_num: int, full_text: str) -> str:
#         text_lower = full_text.lower()
#         if page_num == 1: return "cover"
#         if "isbn" in text_lower and page_num < 10: return "copyright"
#         if ("contents" in text_lower or "table of contents" in text_lower) and page_num < 25: return "toc"
#         if ("preface" in text_lower or "foreword" in text_lower) and page_num < 30: return "preface"
#         if ("bibliography" in text_lower[:200] or "references" in text_lower[:200]) and page_num > 10: return "references"
#         if ("appendix" in text_lower[:200] or "annex" in text_lower[:200]) and page_num > 10: return "appendix"
#         if page_num < 10: return "title"
#         return "body"

#     def _classify_element(self, text: str, font_size: float, is_bold: bool, profile: Dict) -> Tuple[str, int, float]:
#         """
#         Dynamically classifies text based on document typography profile and regex.
#         Returns: (type, heading_level, confidence)
#         """
#         text_clean = text.strip()
#         dom_font = profile["dominant_font"]

#         # 1. Regex Rules (High Confidence)
#         if self.patterns["isbn"].search(text_clean): return ("isbn", 0, 0.99)
#         if self.patterns["doi"].search(text_clean): return ("doi", 0, 0.99)
#         if self.patterns["caption"].match(text_clean): return ("caption", 0, 0.95)
#         if self.patterns["list_item"].match(text_clean): return ("list_item", 0, 0.90)
        
#         # Determine Equation likelihood
#         if self.patterns["equation"].search(text_clean) and len(text_clean) < 100:
#             return ("equation", 0, 0.85)

#         # 2. Dynamic Typography Hierarchy
#         # Compare current font to the dominant body font of the whole book
#         word_count = len(text_clean.split())
#         is_short = word_count < 20
#         ends_with_punctuation = re.search(r'[.?!:]$', text_clean)

#         if is_short and not ends_with_punctuation:
#             if font_size > dom_font * 1.5: return ("heading", 1, 0.95) # Chapter
#             if font_size > dom_font * 1.2: return ("heading", 2, 0.92) # Section
#             if font_size > dom_font and is_bold: return ("heading", 3, 0.88) # Subsection
#             if font_size == dom_font and is_bold: return ("heading", 4, 0.80) # Minor heading

#         return ("paragraph", 0, 0.90)

#     ###########################################################################
#     # STAGE 3: SPATIAL LINKING
#     ###########################################################################

#     def _link_captions_spatially(self, elements: List[Dict]):
#         """Links captions to the closest image or table using Euclidean geometry."""
#         captions = [e for e in elements if e["type"] == "caption"]
#         targets = [e for e in elements if e["type"] in ["image", "table"]]

#         for cap in captions:
#             cx, cy = cap["bbox"][0], cap["bbox"][1]
#             best_target = None
#             min_dist = float('inf')

#             for t in targets:
#                 # Calculate center of target bounding box
#                 tx = (t["bbox"][0] + t["bbox"][2]) / 2
#                 ty = (t["bbox"][1] + t["bbox"][3]) / 2
#                 dist = math.hypot(cx - tx, cy - ty)

#                 # Link if within a reasonable spatial radius (e.g., 200 pts)
#                 if dist < min_dist and dist < 200:
#                     min_dist = dist
#                     best_target = t
            
#             if best_target:
#                 cap["target_element_id"] = best_target["element_id"]
#                 best_target["caption_element_id"] = cap["element_id"]

#     ###########################################################################
#     # STAGE 4: GRAPH & CHUNK BOUNDARY BUILDER
#     ###########################################################################

#     def _build_knowledge_graph(self, elements: List[Dict]) -> Dict[str, Any]:
#         """
#         Builds parent/child trees and assigns semantic_chunk_ids for RAG.
#         """
#         document_graph = {"type": "document", "id": "root", "children": []}
#         stack = [{"level": 0, "node": document_graph, "id": "root", "path": []}]
        
#         current_chunk_id = "chunk_front_matter"

#         for i, el in enumerate(elements):
#             el["previous_id"] = elements[i-1]["element_id"] if i > 0 else None
#             el["next_id"] = elements[i+1]["element_id"] if i < len(elements)-1 else None

#             h_level = el.get("heading_level", 0)
            
#             if el["type"] == "heading":
#                 while len(stack) > 1 and stack[-1]["level"] >= h_level:
#                     stack.pop()
                    
#                 parent = stack[-1]
#                 el["parent_id"] = parent["id"]
#                 current_chunk_id = f"chunk_{el['element_id']}"  # New chunk starts at heading
                
#                 new_node = {
#                     "id": el["element_id"],
#                     "type": "heading",
#                     "text": el["text"],
#                     "level": h_level,
#                     "children": []
#                 }
#                 parent["node"]["children"].append(new_node)
                
#                 new_path = parent["path"] + [el["text"]]
#                 stack.append({"level": h_level, "node": new_node, "id": el["element_id"], "path": new_path})
#                 el["section_path"] = new_path
                
#             else:
#                 parent = stack[-1]
#                 el["parent_id"] = parent["id"]
#                 el["section_path"] = parent["path"]
#                 parent["node"]["children"].append({
#                     "id": el["element_id"],
#                     "type": el["type"]
#                 })

#             # Assign RAG Chunk ID
#             el["semantic_chunk_id"] = current_chunk_id

#             # Cross-reference tagging
#             cross_refs = self.patterns["cross_ref"].findall(el.get("text", ""))
#             if cross_refs:
#                 el["contains_cross_references"] = [" ".join(ref) for ref in cross_refs]

#         return document_graph

#     ###########################################################################
#     # MASTER ORCHESTRATOR
#     ###########################################################################

#     async def build_structural_tree(self, document_id: str) -> Dict[str, Any]:
#         pdf_path = self._locate_pdf(document_id)
#         folders = self._create_output_directories(document_id)

#         try:
#             logger.info(f"Extracting Enterprise-grade Document Intelligence for {document_id}")
#             doc_fitz = fitz.open(str(pdf_path))
#             total_pages = len(doc_fitz)

#             # Stage 1: Profile Typography & Noise
#             doc_profile = self._profile_document(doc_fitz)

#             toc_raw = doc_fitz.get_toc()
#             table_of_contents = [{"level": i[0], "title": i[1].strip(), "page_number": i[2]} for i in toc_raw]

#             global_elements = []  
#             pages_data = []       
#             seq_idx = 1

#             with pdfplumber.open(str(pdf_path)) as doc_plumber:
#                 for page_idx in range(total_pages):
#                     page_num = page_idx + 1
#                     page_fitz = doc_fitz[page_idx]
#                     page_plumber = doc_plumber.pages[page_idx]
#                     rect = page_fitz.rect

#                     full_page_text = chr(12).join([b[4] for b in page_fitz.get_text("blocks")])
#                     page_type = self._classify_page(page_num, full_page_text)

#                     raw_page_elements = []
#                     table_bboxes = []

#                     # 1. TABLES
#                     for t_idx, table_obj in enumerate(page_plumber.find_tables()):
#                         bbox = self._bbox(table_obj.bbox)
#                         table_data = table_obj.extract()
#                         table_bboxes.append(bbox)
#                         raw_page_elements.append({
#                             "element_id": f"{document_id}_p{page_num}_table_{t_idx + 1}",
#                             "type": "table",
#                             "table_index": t_idx + 1,
#                             "bbox": bbox,
#                             "row_count": len(table_data),
#                             "col_count": len(table_data[0]) if table_data else 0,
#                             "rows": table_data,
#                             "confidence": 0.98
#                         })

#                     # 2. IMAGES
#                     for img_idx, img_info in enumerate(page_fitz.get_images(full=True)):
#                         xref = img_info[0]
#                         rects = page_fitz.get_image_rects(xref)
                        
#                         base_image = doc_fitz.extract_image(xref)
#                         image_ext = base_image["ext"]
#                         image_filename = f"page_{page_num}_img_{img_idx + 1}.{image_ext}"
#                         self._save_image(base_image["image"], folders["images"] / image_filename)

#                         for img_rect in rects:
#                             img_area = img_rect.width * img_rect.height
#                             img_type = "figure"
#                             if page_type == "cover": img_type = "cover_image"
#                             elif page_type in ["title", "copyright"] and img_area < 5000: img_type = "logo"

#                             raw_page_elements.append({
#                                 "element_id": f"{document_id}_p{page_num}_img_{img_idx + 1}",
#                                 "type": img_type,
#                                 "image_index": img_idx + 1,
#                                 "xref": xref,
#                                 "bbox": self._bbox([img_rect.x0, img_rect.y0, img_rect.x1, img_rect.y1]),
#                                 "image_path": f"/storage/processed/{document_id}/images/{image_filename}",
#                                 "width": round(img_rect.width, 2),
#                                 "height": round(img_rect.height, 2),
#                                 "confidence": 0.99
#                             })

#                     # 3. TEXT & TYPOGRAPHY
#                     blocks = page_fitz.get_text("dict").get("blocks", [])
#                     if not blocks:
#                         raw_page_elements.append({
#                             "element_id": f"{document_id}_p{page_num}_scanned_{seq_idx}",
#                             "type": "scanned_page",
#                             "text": "",
#                             "bbox": self._bbox([0, 0, rect.width, rect.height]),
#                             "requires_ocr": True,
#                             "confidence": 1.0
#                         })
#                     else:
#                         for block in blocks:
#                             if block.get("type") != 0: continue
#                             block_bbox = self._bbox(block["bbox"])
                            
#                             # Filter Tables and Noise
#                             if self._inside_table(block_bbox, table_bboxes): continue
                            
#                             block_text, max_font, is_bold = "", 0.0, False
#                             for line in block.get("lines", []):
#                                 for span in line.get("spans", []):
#                                     block_text += span.get("text", "")
#                                     if span.get("size", 0) > max_font: max_font = span.get("size", 0)
#                                     if (span.get("flags", 0) & 2) or "bold" in span.get("font", "").lower():
#                                         is_bold = True
#                                 block_text += " "

#                             block_text = block_text.strip()
#                             if not block_text: continue

#                             # Header/Footer Removal
#                             if block_bbox[1] < rect.height * 0.08 and block_text in doc_profile["headers"]:
#                                 raw_page_elements.append({"type": "header", "text": block_text, "bbox": block_bbox, "confidence": 0.95})
#                                 continue
#                             if block_bbox[3] > rect.height * 0.92 and block_text in doc_profile["footers"]:
#                                 raw_page_elements.append({"type": "footer", "text": block_text, "bbox": block_bbox, "confidence": 0.95})
#                                 continue

#                             # Page Numbers
#                             if (block_bbox[1] < rect.height * 0.1 or block_bbox[3] > rect.height * 0.9) and block_text.isdigit():
#                                 raw_page_elements.append({"type": "page_number", "text": block_text, "bbox": block_bbox, "confidence": 0.98})
#                                 continue

#                             # Semantic Classification
#                             el_type, h_level, conf = self._classify_element(block_text, max_font, is_bold, doc_profile)

#                             raw_page_elements.append({
#                                 "type": el_type,
#                                 "heading_level": h_level,
#                                 "text": block_text,
#                                 "font_size": round(max_font, 1),
#                                 "is_bold": is_bold,
#                                 "bbox": block_bbox,
#                                 "confidence": conf
#                             })

#                     # Page Sorting & ID generation (Only feed non-noise elements into the main graph)
#                     filtered_elements = [e for e in raw_page_elements if e["type"] not in ["header", "footer", "page_number"]]
#                     sorted_page_elements = self._sort_reading_order(filtered_elements)
                    
#                     for el in sorted_page_elements:
#                         if "element_id" not in el:
#                             el["element_id"] = f"{document_id}_p{page_num}_{el['type']}_{seq_idx}"
#                         el["page_number"] = page_num
#                         el["page_type"] = page_type
#                         el["reading_sequence"] = seq_idx
#                         global_elements.append(el)
#                         seq_idx += 1

#             doc_fitz.close()

#             # Stage 4: Spatial Linking
#             self._link_captions_spatially(global_elements)

#             # Stage 5: Semantic Graph & Chunks
#             document_graph = self._build_knowledge_graph(global_elements)

#             # Group pages for output
#             for page_num in range(1, total_pages + 1):
#                 page_elems = [e for e in global_elements if e.get("page_number") == page_num]
#                 if not page_elems: continue 
                
#                 pages_data.append({
#                     "page_number": page_num,
#                     "page_type": page_elems[0].get("page_type", "body"),
#                     "elements_count": len(page_elems),
#                     "elements": page_elems,
#                     "full_text": "\n\n".join([e.get("text", "") for e in page_elems if "text" in e])
#                 })

#             # Stage 6: Output Assembly
#             document_tree = {
#                 "document_id": document_id,
#                 "statistics": {
#                     "total_pages": total_pages,
#                     "elements_extracted": len(global_elements),
#                     "dominant_body_font": doc_profile["dominant_font"]
#                 },
#                 "has_native_toc": len(table_of_contents) > 0,
#                 "table_of_contents": table_of_contents,
#                 "document_graph": document_graph,
#                 "pages": pages_data
#             }

#             tree_path = folders["root"] / "document_tree.json"
#             with open(tree_path, "w", encoding="utf-8") as f:
#                 json.dump(document_tree, f, indent=4, ensure_ascii=False)

#             logger.info(f"Successfully compiled Semantic Document Intelligence for {document_id}")
#             return document_tree

#         except Exception as e:
#             logger.error(f"Error building intelligence tree for {document_id}: {str(e)}", exc_info=True)
#             raise ProcessingError(f"Failed to extract document structure: {str(e)}")





        

# import json
# import math
# import re
# from collections import Counter, defaultdict
# from pathlib import Path
# from typing import Any, Dict, List, Tuple

# import pymupdf as fitz
# import pdfplumber

# from app.core.config import settings
# from app.core.exceptions import DocumentNotFoundError, ProcessingError
# from app.core.logger import logger


# class StructureService:
#     """
#     High-performance document structure extraction service.

#     IMPORTANT:
#     - Existing API response structure is preserved.
#     - Existing semantic classification logic is preserved.
#     - Existing document_tree.json structure is preserved.
#     - Existing image/table/text extraction behavior is preserved.
#     """

#     def __init__(self):
#         self.raw_dir = settings.STORAGE_RAW_DIR
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR

#         # ------------------------------------------------------------------
#         # Compile regex patterns once.
#         # ------------------------------------------------------------------
#         self.patterns = {
#             "isbn": re.compile(
#                 r"(?:ISBN(?:-1[03])?:?\s*)?"
#                 r"(?=[-0-9 ]{13,17})"
#                 r"(?:97[89][-\s]?)?"
#                 r"[0-9]{1,5}[-\s]?[0-9]+[-\s]?[0-9]+[-\s]?[0-9X]",
#                 re.IGNORECASE,
#             ),
#             "doi": re.compile(
#                 r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b",
#                 re.IGNORECASE,
#             ),
#             "copyright": re.compile(
#                 r"(©|Copyright)\s*(?:\d{4})",
#                 re.IGNORECASE,
#             ),
#             "edition": re.compile(
#                 r"(\b(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|\d+(st|nd|rd|th))\b\s+Edition)",
#                 re.IGNORECASE,
#             ),
#             "url": re.compile(
#                 r"(https?://[^\s]+|www\.[^\s]+)",
#                 re.IGNORECASE,
#             ),
#             "email": re.compile(
#                 r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
#             ),
#             "caption": re.compile(
#                 r"^(fig\.?|figure|table|chart|plate|scheme|map)\s*\d+",
#                 re.IGNORECASE,
#             ),
#             "list_item": re.compile(
#                 r"^(\d+[\.\)]|[a-zA-Z][\.\)]|[•\-\*])\s+"
#             ),
#             "cross_ref": re.compile(
#                 r"\b(see|refer to)\s+"
#                 r"(figure|fig\.|table|chapter|section|appendix)\s+\d+",
#                 re.IGNORECASE,
#             ),
#             "equation": re.compile(
#                 r"(=|≈|≠|∑|∫|√|Δ|Ω|±|≤|≥)"
#             ),
#             "ending_punctuation": re.compile(r"[.?!:]$"),
#         }

#     # ======================================================================
#     # STAGE 0: I/O HELPERS
#     # ======================================================================

#     def _locate_pdf(self, document_id: str) -> Path:
#         """
#         Locate source PDF.

#         Same behavior as previous implementation.
#         """

#         raw_document_path = self.raw_dir / document_id / "original.pdf"

#         if raw_document_path.exists():
#             return raw_document_path

#         raw_flat_path = self.raw_dir / f"{document_id}.pdf"

#         if raw_flat_path.exists():
#             return raw_flat_path

#         processed_dir = self.processed_dir / document_id

#         if processed_dir.exists():
#             pdf_files = list(processed_dir.glob("*.pdf"))

#             if pdf_files:
#                 return pdf_files[0]

#         raise DocumentNotFoundError(document_id)

#     def _create_output_directories(
#         self,
#         document_id: str,
#     ) -> Dict[str, Path]:
#         """
#         Creates output directories.

#         Same returned structure.
#         """

#         root = self.processed_dir / document_id

#         folders = {
#             "root": root,
#             "images": root / "images",
#             "tables": root / "tables",
#         }

#         # mkdir is cheap and idempotent.
#         for folder in folders.values():
#             folder.mkdir(parents=True, exist_ok=True)

#         return folders

#     @staticmethod
#     def _bbox(bbox) -> List[float]:
#         """
#         Convert bbox coordinates to rounded floats.
#         """

#         return [
#             round(float(bbox[0]), 2),
#             round(float(bbox[1]), 2),
#             round(float(bbox[2]), 2),
#             round(float(bbox[3]), 2),
#         ]

#     @staticmethod
#     def _save_image(
#         image_bytes: bytes,
#         image_path: Path,
#     ) -> None:
#         """
#         Save extracted image.
#         """

#         with open(image_path, "wb") as file:
#             file.write(image_bytes)

#     @staticmethod
#     def _sort_reading_order(
#         elements: List[Dict],
#     ) -> List[Dict]:
#         """
#         Sort elements top-to-bottom and left-to-right.

#         Same ordering logic as original implementation.
#         """

#         return sorted(
#             elements,
#             key=lambda item: (
#                 round(item["bbox"][1] / 10),
#                 round(item["bbox"][0]),
#             ),
#         )

#     @staticmethod
#     def _inside_table(
#         bbox: List[float],
#         table_boxes: List[List[float]],
#     ) -> bool:
#         """
#         Check whether an element bbox is inside a table bbox.

#         Optimized by using local variables.
#         """

#         if not table_boxes:
#             return False

#         x0, y0, x1, y1 = bbox

#         for table_box in table_boxes:
#             tx0, ty0, tx1, ty1 = table_box

#             if (
#                 x0 >= tx0 - 2
#                 and x1 <= tx1 + 2
#                 and y0 >= ty0 - 2
#                 and y1 <= ty1 + 2
#             ):
#                 return True

#         return False

#     # ======================================================================
#     # STAGE 1: DOCUMENT PROFILING
#     # ======================================================================

#     def _profile_document(
#         self,
#         doc_fitz: fitz.Document,
#     ) -> Dict[str, Any]:
#         """
#         Calculates dominant font and repeating headers/footers.

#         Optimization:
#         - Only profiles first 50 pages, as before.
#         - Uses get_text("dict") once per page.
#         - Avoids reconstructing block text with nested comprehensions.
#         """

#         font_sizes: List[int] = []
#         top_texts: List[str] = []
#         bottom_texts: List[str] = []

#         sample_pages = min(len(doc_fitz), 50)

#         for page_idx in range(sample_pages):
#             page = doc_fitz[page_idx]
#             rect = page.rect

#             blocks = page.get_text("dict").get("blocks", [])

#             top_limit = rect.height * 0.08
#             bottom_limit = rect.height * 0.92

#             for block in blocks:

#                 if block.get("type") != 0:
#                     continue

#                 bbox = block["bbox"]

#                 block_text_parts: List[str] = []

#                 lines = block.get("lines", [])

#                 for line in lines:
#                     for span in line.get("spans", []):

#                         text = span.get("text", "")

#                         if text:
#                             block_text_parts.append(text)

#                         size = span.get("size", 0)

#                         if size:
#                             font_sizes.append(round(size))

#                 block_text = "".join(block_text_parts).strip()

#                 if not block_text:
#                     continue

#                 if bbox[1] < top_limit:
#                     top_texts.append(block_text)

#                 if bbox[3] > bottom_limit:
#                     bottom_texts.append(block_text)

#         if not font_sizes:
#             return {
#                 "dominant_font": 12.0,
#                 "headers": set(),
#                 "footers": set(),
#             }

#         dominant_font = Counter(font_sizes).most_common(1)[0][0]

#         top_counter = Counter(top_texts)
#         bottom_counter = Counter(bottom_texts)

#         top_repeats = {
#             text
#             for text, count in top_counter.items()
#             if count > 3
#         }

#         bottom_repeats = {
#             text
#             for text, count in bottom_counter.items()
#             if count > 3
#         }

#         return {
#             "dominant_font": dominant_font,
#             "headers": top_repeats,
#             "footers": bottom_repeats,
#         }

#     # ======================================================================
#     # STAGE 2: PAGE CLASSIFICATION
#     # ======================================================================

#     def _classify_page(
#         self,
#         page_num: int,
#         full_text: str,
#     ) -> str:

#         text_lower = full_text.lower()

#         if page_num == 1:
#             return "cover"

#         if "isbn" in text_lower and page_num < 10:
#             return "copyright"

#         if (
#             "contents" in text_lower
#             or "table of contents" in text_lower
#         ) and page_num < 25:
#             return "toc"

#         if (
#             "preface" in text_lower
#             or "foreword" in text_lower
#         ) and page_num < 30:
#             return "preface"

#         first_200 = text_lower[:200]

#         if (
#             "bibliography" in first_200
#             or "references" in first_200
#         ) and page_num > 10:
#             return "references"

#         if (
#             "appendix" in first_200
#             or "annex" in first_200
#         ) and page_num > 10:
#             return "appendix"

#         if page_num < 10:
#             return "title"

#         return "body"

#     # ======================================================================
#     # STAGE 2: ELEMENT CLASSIFICATION
#     # ======================================================================

#     def _classify_element(
#         self,
#         text: str,
#         font_size: float,
#         is_bold: bool,
#         profile: Dict,
#     ) -> Tuple[str, int, float]:
#         """
#         Classifies extracted text.

#         Logic intentionally preserved.
#         """

#         text_clean = text.strip()

#         dom_font = profile["dominant_font"]

#         # --------------------------------------------------------------
#         # High-confidence semantic patterns
#         # --------------------------------------------------------------

#         if self.patterns["isbn"].search(text_clean):
#             return "isbn", 0, 0.99

#         if self.patterns["doi"].search(text_clean):
#             return "doi", 0, 0.99

#         if self.patterns["caption"].match(text_clean):
#             return "caption", 0, 0.95

#         if self.patterns["list_item"].match(text_clean):
#             return "list_item", 0, 0.90

#         # --------------------------------------------------------------
#         # Equation detection
#         # --------------------------------------------------------------

#         if (
#             len(text_clean) < 100
#             and self.patterns["equation"].search(text_clean)
#         ):
#             return "equation", 0, 0.85

#         # --------------------------------------------------------------
#         # Typography hierarchy
#         # --------------------------------------------------------------

#         word_count = len(text_clean.split())

#         is_short = word_count < 20

#         ends_with_punctuation = bool(
#             self.patterns["ending_punctuation"].search(text_clean)
#         )

#         if is_short and not ends_with_punctuation:

#             if font_size > dom_font * 1.5:
#                 return "heading", 1, 0.95

#             if font_size > dom_font * 1.2:
#                 return "heading", 2, 0.92

#             if font_size > dom_font and is_bold:
#                 return "heading", 3, 0.88

#             if font_size == dom_font and is_bold:
#                 return "heading", 4, 0.80

#         return "paragraph", 0, 0.90

#     # ======================================================================
#     # STAGE 3: SPATIAL LINKING
#     # ======================================================================

#     def _link_captions_spatially(
#         self,
#         elements: List[Dict],
#     ) -> None:
#         """
#         Links captions to closest image/table.

#         Optimization:
#         - Avoids repeated list creation for unrelated elements.
#         - Uses squared distance instead of math.hypot().
#         - Avoids sqrt calculation completely.
#         """

#         captions = []
#         targets = []

#         for element in elements:

#             element_type = element.get("type")

#             if element_type == "caption":
#                 captions.append(element)

#             elif element_type in ("image", "figure", "cover_image", "logo", "table"):
#                 targets.append(element)

#         if not captions or not targets:
#             return

#         max_distance_squared = 200 * 200

#         for caption in captions:

#             bbox = caption["bbox"]

#             cx = bbox[0]
#             cy = bbox[1]

#             best_target = None
#             min_distance_squared = float("inf")

#             for target in targets:

#                 target_bbox = target["bbox"]

#                 tx = (target_bbox[0] + target_bbox[2]) * 0.5
#                 ty = (target_bbox[1] + target_bbox[3]) * 0.5

#                 dx = cx - tx
#                 dy = cy - ty

#                 distance_squared = dx * dx + dy * dy

#                 if (
#                     distance_squared < min_distance_squared
#                     and distance_squared < max_distance_squared
#                 ):
#                     min_distance_squared = distance_squared
#                     best_target = target

#             if best_target:

#                 caption["target_element_id"] = (
#                     best_target["element_id"]
#                 )

#                 best_target["caption_element_id"] = (
#                     caption["element_id"]
#                 )

#     # ======================================================================
#     # STAGE 4: KNOWLEDGE GRAPH
#     # ======================================================================

#     def _build_knowledge_graph(
#         self,
#         elements: List[Dict],
#     ) -> Dict[str, Any]:
#         """
#         Builds parent/child hierarchy and semantic chunks.

#         Same graph output structure.
#         """

#         document_graph = {
#             "type": "document",
#             "id": "root",
#             "children": [],
#         }

#         stack = [
#             {
#                 "level": 0,
#                 "node": document_graph,
#                 "id": "root",
#                 "path": [],
#             }
#         ]

#         current_chunk_id = "chunk_front_matter"

#         previous_element_id = None

#         total_elements = len(elements)

#         for index, element in enumerate(elements):

#             element_id = element["element_id"]

#             element["previous_id"] = previous_element_id

#             if index + 1 < total_elements:
#                 element["next_id"] = elements[index + 1]["element_id"]
#             else:
#                 element["next_id"] = None

#             previous_element_id = element_id

#             heading_level = element.get("heading_level", 0)

#             if element["type"] == "heading":

#                 while (
#                     len(stack) > 1
#                     and stack[-1]["level"] >= heading_level
#                 ):
#                     stack.pop()

#                 parent = stack[-1]

#                 element["parent_id"] = parent["id"]

#                 current_chunk_id = f"chunk_{element_id}"

#                 new_node = {
#                     "id": element_id,
#                     "type": "heading",
#                     "text": element["text"],
#                     "level": heading_level,
#                     "children": [],
#                 }

#                 parent["node"]["children"].append(new_node)

#                 new_path = parent["path"] + [element["text"]]

#                 stack.append(
#                     {
#                         "level": heading_level,
#                         "node": new_node,
#                         "id": element_id,
#                         "path": new_path,
#                     }
#                 )

#                 element["section_path"] = new_path

#             else:

#                 parent = stack[-1]

#                 element["parent_id"] = parent["id"]

#                 element["section_path"] = parent["path"]

#                 parent["node"]["children"].append(
#                     {
#                         "id": element_id,
#                         "type": element["type"],
#                     }
#                 )

#             element["semantic_chunk_id"] = current_chunk_id

#             # Cross references
#             text = element.get("text", "")

#             cross_refs = self.patterns["cross_ref"].findall(text)

#             if cross_refs:
#                 element["contains_cross_references"] = [
#                     " ".join(ref)
#                     for ref in cross_refs
#                 ]

#         return document_graph

#     # ======================================================================
#     # MASTER ORCHESTRATOR
#     # ======================================================================

#     async def build_structural_tree(
#         self,
#         document_id: str,
#     ) -> Dict[str, Any]:

#         pdf_path = self._locate_pdf(document_id)

#         folders = self._create_output_directories(document_id)

#         logger.info(
#             f"Extracting Enterprise-grade Document Intelligence "
#             f"for {document_id}"
#         )

#         doc_fitz = None

#         try:

#             # ==============================================================
#             # OPEN PDF
#             # ==============================================================

#             doc_fitz = fitz.open(str(pdf_path))

#             total_pages = len(doc_fitz)

#             # ==============================================================
#             # STAGE 1: DOCUMENT PROFILE
#             # ==============================================================

#             doc_profile = self._profile_document(doc_fitz)

#             # ==============================================================
#             # NATIVE TOC
#             # ==============================================================

#             toc_raw = doc_fitz.get_toc()

#             table_of_contents = [
#                 {
#                     "level": item[0],
#                     "title": item[1].strip(),
#                     "page_number": item[2],
#                 }
#                 for item in toc_raw
#             ]

#             # ==============================================================
#             # MAIN EXTRACTION ARRAYS
#             # ==============================================================

#             global_elements: List[Dict] = []

#             seq_idx = 1

#             # ==============================================================
#             # PDFPLUMBER
#             #
#             # Kept because table extraction behavior must remain the same.
#             # ==============================================================

#             with pdfplumber.open(str(pdf_path)) as doc_plumber:

#                 for page_idx in range(total_pages):

#                     page_num = page_idx + 1

#                     page_fitz = doc_fitz[page_idx]

#                     page_plumber = doc_plumber.pages[page_idx]

#                     rect = page_fitz.rect

#                     # ======================================================
#                     # GET TEXT DICT ONLY ONCE
#                     #
#                     # Original implementation did:
#                     #   get_text("blocks")
#                     #   get_text("dict")
#                     #
#                     # This version does only get_text("dict").
#                     # ======================================================

#                     text_dict = page_fitz.get_text("dict")

#                     blocks = text_dict.get("blocks", [])

#                     # ======================================================
#                     # BUILD FULL PAGE TEXT FROM SAME TEXT BLOCK DATA
#                     # ======================================================

#                     full_text_parts = []

#                     for block in blocks:

#                         if block.get("type") != 0:
#                             continue

#                         block_text_parts = []

#                         for line in block.get("lines", []):

#                             for span in line.get("spans", []):

#                                 span_text = span.get("text", "")

#                                 if span_text:
#                                     block_text_parts.append(span_text)

#                         if block_text_parts:
#                             full_text_parts.append(
#                                 "".join(block_text_parts)
#                             )

#                     full_page_text = "\f".join(full_text_parts)

#                     page_type = self._classify_page(
#                         page_num,
#                         full_page_text,
#                     )

#                     raw_page_elements: List[Dict] = []

#                     table_bboxes: List[List[float]] = []

#                     # ======================================================
#                     # 1. TABLES
#                     #
#                     # This remains the most expensive operation.
#                     # It is retained because API/output behavior must remain.
#                     # ======================================================

#                     tables = page_plumber.find_tables()

#                     for table_idx, table_obj in enumerate(tables):

#                         bbox = self._bbox(table_obj.bbox)

#                         table_data = table_obj.extract()

#                         table_bboxes.append(bbox)

#                         raw_page_elements.append(
#                             {
#                                 "element_id": (
#                                     f"{document_id}_p{page_num}"
#                                     f"_table_{table_idx + 1}"
#                                 ),
#                                 "type": "table",
#                                 "table_index": table_idx + 1,
#                                 "bbox": bbox,
#                                 "row_count": len(table_data),
#                                 "col_count": (
#                                     len(table_data[0])
#                                     if table_data
#                                     else 0
#                                 ),
#                                 "rows": table_data,
#                                 "confidence": 0.98,
#                             }
#                         )

#                     # ======================================================
#                     # 2. IMAGES
#                     # ======================================================

#                     image_list = page_fitz.get_images(full=True)

#                     for img_idx, img_info in enumerate(image_list):

#                         xref = img_info[0]

#                         rects = page_fitz.get_image_rects(xref)

#                         # Extract image once.
#                         base_image = doc_fitz.extract_image(xref)

#                         image_ext = base_image["ext"]

#                         image_filename = (
#                             f"page_{page_num}"
#                             f"_img_{img_idx + 1}"
#                             f".{image_ext}"
#                         )

#                         image_path = (
#                             folders["images"] / image_filename
#                         )

#                         self._save_image(
#                             base_image["image"],
#                             image_path,
#                         )

#                         for img_rect in rects:

#                             img_area = (
#                                 img_rect.width
#                                 * img_rect.height
#                             )

#                             img_type = "figure"

#                             if page_type == "cover":
#                                 img_type = "cover_image"

#                             elif (
#                                 page_type in ("title", "copyright")
#                                 and img_area < 5000
#                             ):
#                                 img_type = "logo"

#                             raw_page_elements.append(
#                                 {
#                                     "element_id": (
#                                         f"{document_id}_p{page_num}"
#                                         f"_img_{img_idx + 1}"
#                                     ),
#                                     "type": img_type,
#                                     "image_index": img_idx + 1,
#                                     "xref": xref,
#                                     "bbox": self._bbox(
#                                         [
#                                             img_rect.x0,
#                                             img_rect.y0,
#                                             img_rect.x1,
#                                             img_rect.y1,
#                                         ]
#                                     ),
#                                     "image_path": (
#                                         f"/storage/processed/"
#                                         f"{document_id}/images/"
#                                         f"{image_filename}"
#                                     ),
#                                     "width": round(
#                                         img_rect.width,
#                                         2,
#                                     ),
#                                     "height": round(
#                                         img_rect.height,
#                                         2,
#                                     ),
#                                     "confidence": 0.99,
#                                 }
#                             )

#                     # ======================================================
#                     # 3. TEXT & TYPOGRAPHY
#                     # ======================================================

#                     if not blocks:

#                         raw_page_elements.append(
#                             {
#                                 "element_id": (
#                                     f"{document_id}_p{page_num}"
#                                     f"_scanned_{seq_idx}"
#                                 ),
#                                 "type": "scanned_page",
#                                 "text": "",
#                                 "bbox": self._bbox(
#                                     [
#                                         0,
#                                         0,
#                                         rect.width,
#                                         rect.height,
#                                     ]
#                                 ),
#                                 "requires_ocr": True,
#                                 "confidence": 1.0,
#                             }
#                         )

#                     else:

#                         top_header_limit = rect.height * 0.08
#                         bottom_footer_limit = rect.height * 0.92

#                         for block in blocks:

#                             if block.get("type") != 0:
#                                 continue

#                             block_bbox = self._bbox(
#                                 block["bbox"]
#                             )

#                             # --------------------------------------------------
#                             # Table filtering
#                             # --------------------------------------------------

#                             if self._inside_table(
#                                 block_bbox,
#                                 table_bboxes,
#                             ):
#                                 continue

#                             # --------------------------------------------------
#                             # Extract block text + typography
#                             # --------------------------------------------------

#                             text_parts: List[str] = []

#                             max_font = 0.0

#                             is_bold = False

#                             for line in block.get("lines", []):

#                                 for span in line.get(
#                                     "spans",
#                                     [],
#                                 ):

#                                     span_text = span.get(
#                                         "text",
#                                         "",
#                                     )

#                                     if span_text:
#                                         text_parts.append(
#                                             span_text
#                                         )

#                                     span_size = span.get(
#                                         "size",
#                                         0,
#                                     )

#                                     if span_size > max_font:
#                                         max_font = span_size

#                                     span_flags = span.get(
#                                         "flags",
#                                         0,
#                                     )

#                                     span_font = span.get(
#                                         "font",
#                                         "",
#                                     )

#                                     if (
#                                         span_flags & 2
#                                         or "bold"
#                                         in span_font.lower()
#                                     ):
#                                         is_bold = True

#                             block_text = "".join(
#                                 text_parts
#                             ).strip()

#                             if not block_text:
#                                 continue

#                             # --------------------------------------------------
#                             # Header
#                             # --------------------------------------------------

#                             if (
#                                 block_bbox[1]
#                                 < top_header_limit
#                                 and block_text
#                                 in doc_profile["headers"]
#                             ):

#                                 raw_page_elements.append(
#                                     {
#                                         "type": "header",
#                                         "text": block_text,
#                                         "bbox": block_bbox,
#                                         "confidence": 0.95,
#                                     }
#                                 )

#                                 continue

#                             # --------------------------------------------------
#                             # Footer
#                             # --------------------------------------------------

#                             if (
#                                 block_bbox[3]
#                                 > bottom_footer_limit
#                                 and block_text
#                                 in doc_profile["footers"]
#                             ):

#                                 raw_page_elements.append(
#                                     {
#                                         "type": "footer",
#                                         "text": block_text,
#                                         "bbox": block_bbox,
#                                         "confidence": 0.95,
#                                     }
#                                 )

#                                 continue

#                             # --------------------------------------------------
#                             # Page number
#                             # --------------------------------------------------

#                             if (
#                                 (
#                                     block_bbox[1]
#                                     < rect.height * 0.1
#                                 )
#                                 or (
#                                     block_bbox[3]
#                                     > rect.height * 0.9
#                                 )
#                             ) and block_text.isdigit():

#                                 raw_page_elements.append(
#                                     {
#                                         "type": "page_number",
#                                         "text": block_text,
#                                         "bbox": block_bbox,
#                                         "confidence": 0.98,
#                                     }
#                                 )

#                                 continue

#                             # --------------------------------------------------
#                             # Semantic classification
#                             # --------------------------------------------------

#                             (
#                                 element_type,
#                                 heading_level,
#                                 confidence,
#                             ) = self._classify_element(
#                                 block_text,
#                                 max_font,
#                                 is_bold,
#                                 doc_profile,
#                             )

#                             raw_page_elements.append(
#                                 {
#                                     "type": element_type,
#                                     "heading_level": heading_level,
#                                     "text": block_text,
#                                     "font_size": round(
#                                         max_font,
#                                         1,
#                                     ),
#                                     "is_bold": is_bold,
#                                     "bbox": block_bbox,
#                                     "confidence": confidence,
#                                 }
#                             )

#                     # ======================================================
#                     # PAGE SORTING
#                     # ======================================================

#                     filtered_elements = [
#                         element
#                         for element in raw_page_elements
#                         if element["type"]
#                         not in (
#                             "header",
#                             "footer",
#                             "page_number",
#                         )
#                     ]

#                     sorted_page_elements = (
#                         self._sort_reading_order(
#                             filtered_elements
#                         )
#                     )

#                     # ======================================================
#                     # ADD PAGE METADATA
#                     # ======================================================

#                     for element in sorted_page_elements:

#                         if "element_id" not in element:

#                             element["element_id"] = (
#                                 f"{document_id}_p{page_num}_"
#                                 f"{element['type']}_{seq_idx}"
#                             )

#                         element["page_number"] = page_num

#                         element["page_type"] = page_type

#                         element["reading_sequence"] = seq_idx

#                         global_elements.append(element)

#                         seq_idx += 1

#             # ==============================================================
#             # CLOSE FITZ BEFORE POST-PROCESSING
#             # ==============================================================

#             doc_fitz.close()
#             doc_fitz = None

#             # ==============================================================
#             # STAGE 4: SPATIAL LINKING
#             # ==============================================================

#             self._link_captions_spatially(
#                 global_elements
#             )

#             # ==============================================================
#             # STAGE 5: SEMANTIC GRAPH
#             # ==============================================================

#             document_graph = self._build_knowledge_graph(
#                 global_elements
#             )

#             # ==============================================================
#             # GROUP ELEMENTS BY PAGE
#             #
#             # Original implementation repeatedly scanned global_elements
#             # for every page.
#             #
#             # This version performs one pass only.
#             # ==============================================================

#             elements_by_page = defaultdict(list)

#             for element in global_elements:
#                 elements_by_page[
#                     element["page_number"]
#                 ].append(element)

#             pages_data: List[Dict] = []

#             for page_num in range(
#                 1,
#                 total_pages + 1,
#             ):

#                 page_elements = elements_by_page.get(
#                     page_num
#                 )

#                 if not page_elements:
#                     continue

#                 page_text_parts = [
#                     element.get("text", "")
#                     for element in page_elements
#                     if "text" in element
#                 ]

#                 pages_data.append(
#                     {
#                         "page_number": page_num,
#                         "page_type": page_elements[0].get(
#                             "page_type",
#                             "body",
#                         ),
#                         "elements_count": len(
#                             page_elements
#                         ),
#                         "elements": page_elements,
#                         "full_text": "\n\n".join(
#                             page_text_parts
#                         ),
#                     }
#                 )

#             # ==============================================================
#             # STAGE 6: OUTPUT ASSEMBLY
#             # ==============================================================

#             document_tree = {
#                 "document_id": document_id,
#                 "statistics": {
#                     "total_pages": total_pages,
#                     "elements_extracted": len(
#                         global_elements
#                     ),
#                     "dominant_body_font": (
#                         doc_profile["dominant_font"]
#                     ),
#                 },
#                 "has_native_toc": len(
#                     table_of_contents
#                 )
#                 > 0,
#                 "table_of_contents": table_of_contents,
#                 "document_graph": document_graph,
#                 "pages": pages_data,
#             }

#             # ==============================================================
#             # WRITE JSON
#             # ==============================================================

#             tree_path = (
#                 folders["root"]
#                 / "document_tree.json"
#             )

#             with open(
#                 tree_path,
#                 "w",
#                 encoding="utf-8",
#             ) as file:

#                 json.dump(
#                     document_tree,
#                     file,
#                     indent=4,
#                     ensure_ascii=False,
#                 )

#             logger.info(
#                 f"Successfully compiled Semantic "
#                 f"Document Intelligence for {document_id}"
#             )

#             return document_tree

#         except Exception as e:

#             logger.error(
#                 f"Error building intelligence tree "
#                 f"for {document_id}: {str(e)}",
#                 exc_info=True,
#             )

#             raise ProcessingError(
#                 f"Failed to extract document structure: {str(e)}"
#             )

#         finally:

#             # Safety cleanup if an exception occurs.
#             if doc_fitz is not None:

#                 try:
#                     doc_fitz.close()
#                 except Exception:
#                     pass