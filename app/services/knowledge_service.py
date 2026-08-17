# # import json
# # from pathlib import Path
# # from app.core.config import settings
# # from app.core.exceptions import DocumentNotFoundError, StorageError
# # from app.core.logger import logger

# # class KnowledgeService:
# #     def __init__(self):
# #         self.raw_dir = settings.STORAGE_RAW_DIR
# #         self.processed_dir = settings.STORAGE_PROCESSED_DIR

# #     def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 150) -> list[dict]:
# #         """Splits page text into overlapping semantic chunks for downstream embeddings."""
# #         chunks = []
# #         if not text.strip():
# #             return chunks

# #         start = 0
# #         text_length = len(text)

# #         while start < text_length:
# #             end = min(start + chunk_size, text_length)
            
# #             # Adjust end to nearest space boundary to avoid cutting words
# #             if end < text_length:
# #                 last_space = text.rfind(" ", start, end)
# #                 if last_space != -1 and last_space > start:
# #                     end = last_space

# #             chunk_content = text[start:end].strip()
# #             if chunk_content:
# #                 chunks.append({
# #                     "content": chunk_content,
# #                     "start_char": start,
# #                     "end_char": end,
# #                     "char_count": len(chunk_content),
# #                     "word_count": len(chunk_content.split())
# #                 })

# #             start = end - overlap if (end - overlap) > start else end

# #         return chunks

# #     async def extract_knowledge(self, document_id: str, chunk_size: int = 1000, overlap: int = 150) -> dict:
# #         """Processes extracted pages into chunked knowledge nodes and writes extracted_knowledge.json."""
# #         processed_base = self.processed_dir / document_id
# #         tree_path = processed_base / "document_tree.json"
# #         metadata_path = self.raw_dir / document_id / "metadata.json"

# #         if not tree_path.exists():
# #             raise DocumentNotFoundError(f"Document tree for {document_id} not found. Run process step first.")

# #         try:
# #             logger.info(f"Extracting knowledge & chunking for {document_id}")
            
# #             with open(tree_path, "r", encoding="utf-8") as f:
# #                 doc_tree = json.load(f)

# #             knowledge_chunks = []
# #             chunk_global_id = 1

# #             for page_info in doc_tree.get("pages", []):
# #                 page_num = page_info["page_number"]
# #                 page_file_path = processed_base / "pages" / f"page_{page_num}.txt"

# #                 if not page_file_path.exists():
# #                     continue

# #                 with open(page_file_path, "r", encoding="utf-8") as pf:
# #                     page_text = pf.read()

# #                 page_chunks = self._chunk_text(page_text, chunk_size=chunk_size, overlap=overlap)

# #                 for chunk in page_chunks:
# #                     chunk_data = {
# #                         "chunk_id": f"chk_{document_id}_{chunk_global_id:05d}",
# #                         "document_id": document_id,
# #                         "page_number": page_num,
# #                         "global_index": chunk_global_id,
# #                         "content": chunk["content"],
# #                         "char_count": chunk["char_count"],
# #                         "word_count": chunk["word_count"],
# #                         "source_location": {
# #                             "start_char": chunk["start_char"],
# #                             "end_char": chunk["end_char"]
# #                         }
# #                     }
# #                     knowledge_chunks.append(chunk_data)
# #                     chunk_global_id += 1

# #             knowledge_payload = {
# #                 "document_id": document_id,
# #                 "total_chunks": len(knowledge_chunks),
# #                 "chunking_config": {
# #                     "chunk_size": chunk_size,
# #                     "overlap": overlap
# #                 },
# #                 "chunks": knowledge_chunks
# #             }

# #             extracted_knowledge_path = processed_base / "extracted_knowledge.json"
# #             with open(extracted_knowledge_path, "w", encoding="utf-8") as kf:
# #                 json.dump(knowledge_payload, kf, indent=2)

# #             # Update status in metadata.json
# #             if metadata_path.exists():
# #                 with open(metadata_path, "r+", encoding="utf-8") as mf:
# #                     meta_data = json.load(mf)
# #                     meta_data["pipeline_status"] = "KNOWLEDGE_EXTRACTED"
# #                     meta_data["next_step"] = f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
# #                     mf.seek(0)
# #                     json.dump(meta_data, mf, indent=2)
# #                     mf.truncate()

# #             logger.info(f"Successfully created {len(knowledge_chunks)} chunks for {document_id}")

# #             return {
# #                 "document_id": document_id,
# #                 "pipeline_status": "KNOWLEDGE_EXTRACTED",
# #                 "total_chunks_created": len(knowledge_chunks),
# #                 "knowledge_artifact_path": str(extracted_knowledge_path.relative_to(settings.BASE_DIR)),
# #                 "next_step": f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
# #             }

# #         except Exception as e:
# #             logger.error(f"Knowledge extraction failed for {document_id}: {str(e)}")
# #             raise StorageError(f"Knowledge extraction failed: {str(e)}")










# # import json
# # from typing import Dict, Any, List
# # from openai import AsyncOpenAI
# # from app.core.config import settings
# # from app.core.exceptions import DocumentNotFoundError, ProcessingError
# # from app.core.logger import logger
# # from app.models.knowledge import KnowledgeExtractionPayload

# # class KnowledgeService:
# #     def __init__(self):
# #         self.raw_dir = settings.STORAGE_RAW_DIR
# #         self.processed_dir = settings.STORAGE_PROCESSED_DIR
# #         self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# #     def _format_unchunked_page_layout(self, page: Dict[str, Any]) -> str:
# #         """
# #         Aggregates text blocks, table matrices, and image bounds page-by-page 
# #         into a unified, unchunked context payload for the LLM. 
# #         NO token chunking or arbitrary splitting is performed.
# #         """
# #         page_num = page.get("page_number")
# #         lines = [f"=== DOCUMENT PAGE {page_num} ==="]

# #         for element in page.get("elements", []):
# #             elem_type = element.get("type")
            
# #             if elem_type in ["heading", "paragraph"]:
# #                 text = element.get("text", "").strip()
# #                 if text:
# #                     lines.append(f"[{elem_type.upper()}] {text}")
            
# #             elif elem_type == "table":
# #                 rows = element.get("rows", [])
# #                 lines.append(f"[TABLE index_{element.get('table_index')}]")
# #                 for row in rows:
# #                     row_content = " | ".join([str(cell or "").strip() for cell in row])
# #                     lines.append(f"| {row_content} |")
            
# #             elif elem_type == "image":
# #                 lines.append(f"[IMAGE asset: index_{element.get('image_index')} at bbox {element.get('bbox')}]")

# #         return "\n".join(lines)

# #     async def extract_knowledge(self, document_id: str) -> dict:
# #         """
# #         Passes unchunked page layouts directly to the LLM to construct 
# #         concepts, definitions, categories, and relational edges.
# #         """
# #         processed_base = self.processed_dir / document_id
# #         tree_path = processed_base / "document_tree.json"
# #         metadata_path = self.raw_dir / document_id / "metadata.json"

# #         if not tree_path.exists():
# #             raise DocumentNotFoundError(f"Document structure tree for {document_id} not found. Run /extract-structure first.")

# #         try:
# #             logger.info(f"Starting unchunked LLM knowledge extraction for {document_id}")
            
# #             with open(tree_path, "r", encoding="utf-8") as f:
# #                 document_tree = json.load(f)

# #             master_knowledge = {
# #                 "document_id": document_id,
# #                 "concepts": [],
# #                 "relationships": [],
# #                 "scientific_rules": [],
# #                 "procedures": []
# #             }

# #             pages = document_tree.get("pages", [])
# #             for page in pages:
# #                 page_num = page.get("page_number")
                
# #                 # Format page layout without chunking
# #                 page_payload = self._format_unchunked_page_layout(page)
                
# #                 # Skip blank or cover pages with minimal content
# #                 if len(page_payload.strip()) < 100:
# #                     continue

# #                 logger.debug(f"Sending unchunked page {page_num} layout to LLM for relationship & node extraction...")
                
# #                 # OpenAI Structured Output guarantees exact alignment with KnowledgeExtractionPayload
# #                 completion = await self.client.beta.chat.completions.parse(
# #                     model="gpt-4o-mini",
# #                     messages=[
# #                         {
# #                             "role": "system", 
# #                             "content": (
# #                                 "You are an expert scientific knowledge extraction engine. "
# #                                 "You are given complete, unchunked document page layouts containing text, table matrices, and image references. "
# #                                 "Your task is to analyze the entire page context and extract scientific concepts, nodes, subnodes, "
# #                                 "and precise relationship edges into the structured schema. Never split concepts arbitrarily."
# #                             )
# #                         },
# #                         {
# #                             "role": "user", 
# #                             "content": f"Extract all concepts, nodes, subnodes, and relationships from this unchunked page layout:\n\n{page_payload}"
# #                         }
# #                     ],
# #                     response_format=KnowledgeExtractionPayload,
# #                     temperature=0.1
# #                 )

# #                 extracted_data = completion.choices[0].message.parsed
                
# #                 if extracted_data:
# #                     master_knowledge["concepts"].extend([c.model_dump() for c in extracted_data.concepts])
# #                     master_knowledge["relationships"].extend([r.model_dump() for r in extracted_data.relationships])
# #                     master_knowledge["scientific_rules"].extend([sr.model_dump() for sr in extracted_data.scientific_rules])
# #                     master_knowledge["procedures"].extend([p.model_dump() for p in extracted_data.procedures])

# #             # Save the clean knowledge graph artifact
# #             extracted_knowledge_path = processed_base / "extracted_knowledge.json"
# #             with open(extracted_knowledge_path, "w", encoding="utf-8") as kf:
# #                 json.dump(master_knowledge, kf, indent=4)

# #             # Update status in metadata.json
# #             if metadata_path.exists():
# #                 with open(metadata_path, "r+", encoding="utf-8") as mf:
# #                     meta_data = json.load(mf)
# #                     meta_data["pipeline_status"] = "KNOWLEDGE_EXTRACTED"
# #                     meta_data["next_step"] = f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
# #                     mf.seek(0)
# #                     json.dump(meta_data, mf, indent=2)
# #                     mf.truncate()

# #             logger.info(f"Successfully extracted {len(master_knowledge['concepts'])} concepts and {len(master_knowledge['relationships'])} relationships for {document_id}")

# #             return {
# #                 "document_id": document_id,
# #                 "pipeline_status": "KNOWLEDGE_EXTRACTED",
# #                 "extracted_stats": {
# #                     "concepts_extracted": len(master_knowledge["concepts"]),
# #                     "relationships_extracted": len(master_knowledge["relationships"])
# #                 },
# #                 "knowledge_artifact_path": str(extracted_knowledge_path.relative_to(settings.BASE_DIR))
# #             }

# #         except Exception as e:
# #             logger.error(f"Unchunked knowledge extraction failed for {document_id}: {str(e)}", exc_info=True)
# #             raise StorageError(f"Knowledge extraction failed: {str(e)}")





# # import json
# # import asyncio
# # from typing import Dict, Any, List
# # from openai import AsyncOpenAI
# # from app.core.config import settings
# # from app.core.exceptions import DocumentNotFoundError, ProcessingError
# # from app.core.logger import logger
# # from app.models.knowledge import KnowledgeExtractionPayload

# # class KnowledgeService:
# #     def __init__(self):
# #         self.raw_dir = settings.STORAGE_RAW_DIR
# #         self.processed_dir = settings.STORAGE_PROCESSED_DIR
# #         # Using model optimized for speed & high accuracy structured extraction
# #         self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
# #         self.model_name = "gpt-4o-mini" # (or "gpt-5.5-mini" when globally available in your environment)

# #     def _format_unchunked_page_payload(self, page: Dict[str, Any]) -> str:
# #         """
# #         Aggregates text blocks, 2D table matrices, and layout headings page-by-page 
# #         into a unified context payload. NO token chunking is performed.
# #         """
# #         page_num = page.get("page_number")
# #         lines = [f"=== DOCUMENT PAGE {page_num} ==="]

# #         for element in page.get("elements", []):
# #             elem_type = element.get("type")
            
# #             if elem_type in ["heading", "paragraph"]:
# #                 text = element.get("text", "").strip()
# #                 if text:
# #                     lines.append(f"[{elem_type.upper()}] {text}")
            
# #             elif elem_type == "table":
# #                 rows = element.get("rows", [])
# #                 lines.append(f"[TABLE index_{element.get('table_index')}]")
# #                 for row in rows:
# #                     row_content = " | ".join([str(cell or "").strip() for cell in row])
# #                     lines.append(f"| {row_content} |")

# #         return "\n".join(lines)

# #     async def _process_single_page(self, page: Dict[str, Any]) -> Dict[str, List[Any]]:
# #         """Sends an unchunked page layout to the LLM for high-speed node/relationship extraction."""
# #         page_num = page.get("page_number")
# #         page_payload = self._format_unchunked_page_payload(page)
        
# #         # Skip blank/sparse pages
# #         if len(page_payload.strip()) < 150:
# #             return {"concepts": [], "relationships": [], "scientific_rules": [], "procedures": []}

# #         try:
# #             logger.debug(f"Extracting unchunked knowledge from page {page_num}...")
            
# #             completion = await self.client.beta.chat.completions.parse(
# #                 model=self.model_name,
# #                 messages=[
# #                     {
# #                         "role": "system", 
# #                         "content": (
# #                             "You are an expert scientific knowledge extraction engine. "
# #                             "Analyze the complete, unchunked page context (text, headings, tables) "
# #                             "and extract precise scientific concepts, nodes, subnodes, and relationship edges "
# #                             "into the structured schema. Do not chunk or split arbitrarily."
# #                         )
# #                     },
# #                     {
# #                         "role": "user", 
# #                         "content": f"Extract all concepts, definitions, and relationships from this unchunked page:\n\n{page_payload}"
# #                     }
# #                 ],
# #                 response_format=KnowledgeExtractionPayload,
# #                 temperature=0.1
# #             )

# #             result = completion.choices[0].message.parsed
# #             if result:
# #                 return {
# #                     "concepts": [c.model_dump() for c in result.concepts],
# #                     "relationships": [r.model_dump() for r in result.relationships],
# #                     "scientific_rules": [sr.model_dump() for sr in result.scientific_rules],
# #                     "procedures": [p.model_dump() for p in result.procedures]
# #                 }
# #         except Exception as e:
# #             logger.error(f"LLM extraction error on page {page_num}: {str(e)}")
            
# #         return {"concepts": [], "relationships": [], "scientific_rules": [], "procedures": []}

# #     async def extract_knowledge(self, document_id: str) -> dict:
# #         processed_base = self.processed_dir / document_id
# #         tree_path = processed_base / "document_tree.json"
# #         metadata_path = self.raw_dir / document_id / "metadata.json"

# #         if not tree_path.exists():
# #             raise DocumentNotFoundError(f"Document structure tree for {document_id} not found. Run /extract-structure first.")

# #         try:
# #             logger.info(f"Starting optimized unchunked LLM extraction for {document_id}")
            
# #             with open(tree_path, "r", encoding="utf-8") as f:
# #                 document_tree = json.load(f)

# #             master_knowledge = {
# #                 "document_id": document_id,
# #                 "concepts": [],
# #                 "relationships": [],
# #                 "scientific_rules": [],
# #                 "procedures": []
# #             }

# #             pages = document_tree.get("pages", [])
            
# #             # OPTIMIZATION FOR SPEED: Process pages concurrently in batches of 5 to maximize throughput
# #             batch_size = 5
# #             for i in range(0, len(pages), batch_size):
# #                 batch = pages[i:i + batch_size]
# #                 tasks = [self._process_single_page(page) for page in batch]
# #                 batch_results = await asyncio.gather(*tasks)

# #                 for res in batch_results:
# #                     master_knowledge["concepts"].extend(res["concepts"])
# #                     master_knowledge["relationships"].extend(res["relationships"])
# #                     master_knowledge["scientific_rules"].extend(res["scientific_rules"])
# #                     master_knowledge["procedures"].extend(res["procedures"])

# #             # Save the clean knowledge graph artifact
# #             extracted_knowledge_path = processed_base / "extracted_knowledge.json"
# #             with open(extracted_knowledge_path, "w", encoding="utf-8") as kf:
# #                 json.dump(master_knowledge, kf, indent=4)

# #             # Update status in metadata.json
# #             if metadata_path.exists():
# #                 with open(metadata_path, "r+", encoding="utf-8") as mf:
# #                     meta_data = json.load(mf)
# #                     meta_data["pipeline_status"] = "KNOWLEDGE_EXTRACTED"
# #                     meta_data["next_step"] = f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
# #                     mf.seek(0)
# #                     json.dump(meta_data, mf, indent=2)
# #                     mf.truncate()

# #             logger.info(f"Successfully extracted {len(master_knowledge['concepts'])} concepts and {len(master_knowledge['relationships'])} relationships for {document_id}")

# #             return {
# #                 "document_id": document_id,
# #                 "pipeline_status": "KNOWLEDGE_EXTRACTED",
# #                 "extracted_stats": {
# #                     "concepts_extracted": len(master_knowledge["concepts"]),
# #                     "relationships_extracted": len(master_knowledge["relationships"])
# #                 },
# #                 "knowledge_artifact_path": str(extracted_knowledge_path.relative_to(settings.BASE_DIR))
# #             }

# #         except Exception as e:
# #             logger.error(f"Knowledge extraction failed for {document_id}: {str(e)}", exc_info=True)
# #             raise StorageError(f"Knowledge extraction failed: {str(e)}")






# # import json
# # import asyncio
# # from typing import Dict, Any, List
# # from openai import AsyncOpenAI

# # from app.core.config import settings
# # from app.core.exceptions import DocumentNotFoundError, ProcessingError, StorageError
# # from app.core.logger import logger
# # from app.models.knowledge import KnowledgeExtractionPayload


# # class KnowledgeService:
# #     def __init__(self):
# #         self.raw_dir = settings.STORAGE_RAW_DIR
# #         self.processed_dir = settings.STORAGE_PROCESSED_DIR
        
# #         self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
# #         self.model_name = "gpt-4o-mini"
        
# #         # Concurrency limit for OpenAI API to prevent rate limits
# #         self.max_concurrent_requests = getattr(settings, "MAX_CONCURRENT_EXTRACTIONS", 5)

# #     def _format_section_payload(self, section_path: List[str], elements: List[Dict]) -> str:
# #         """
# #         Aggregates text, tables, lists, and captions for an entire semantic section,
# #         regardless of how many pages the section spans.
# #         """
# #         path_str = " > ".join(section_path) if section_path else "Root Document"
# #         pages = sorted(list(set([e.get("page_number") for e in elements if e.get("page_number")])))
# #         page_str = f"Pages: {pages[0]} - {pages[-1]}" if len(pages) > 1 else f"Page: {pages[0]}" if pages else ""

# #         lines = [
# #             "=== SECTION CONTEXT ===",
# #             f"Hierarchy: {path_str}",
# #             f"{page_str}",
# #             "\n=== CONTENT ==="
# #         ]

# #         for el in elements:
# #             t = el.get("type", "paragraph")
            
# #             # Text-based elements
# #             if t in ["heading", "paragraph", "caption", "list_item", "equation", "cross_ref"]:
# #                 lines.append(f"[{t.upper()}] {el.get('text', '').strip()}")
            
# #             # Tables formatted as clean Markdown
# #             elif t == "table":
# #                 lines.append(f"[TABLE index_{el.get('table_index', '0')}]")
# #                 for row in el.get("rows", []):
# #                     row_content = " | ".join([str(cell or "").strip() for cell in row])
# #                     lines.append(f"| {row_content} |")
                    
# #             # Image placeholders so the LLM knows a visual exists here
# #             elif t in ["image", "figure", "diagram", "photo"]:
# #                 lines.append(f"[FIGURE ref={el.get('element_id', 'unknown')}]")

# #         return "\n".join(lines)

# #     async def _process_semantic_section(self, chunk_id: str, data: Dict[str, Any]) -> Dict[str, List[Any]]:
# #         """Sends a complete, context-aware section to the LLM for domain knowledge extraction."""
# #         section_path = data.get("path", [])
# #         elements = data.get("elements", [])
        
# #         section_payload = self._format_section_payload(section_path, elements)
        
# #         # Skip sections with negligible text (e.g., just an image and a 2-word caption)
# #         if len(section_payload.strip()) < 150:
# #             return {"concepts": [], "relationships": [], "scientific_rules": [], "procedures": []}

# #         path_str = " > ".join(section_path) if section_path else "Root"
# #         first_page = elements[0].get("page_number") if elements else None

# #         try:
# #             logger.debug(f"Extracting knowledge from section chunk: {chunk_id} ({path_str})")
            
# #             completion = await self.client.beta.chat.completions.parse(
# #                 model=self.model_name,
# #                 messages=[
# #                     {
# #                         "role": "system", 
# #                         "content": (
# #                             "You are an expert scientific knowledge extraction engine.\n"
# #                             "STRICT DIRECTIVES:\n"
# #                             "1. EXTRACT ONLY DOMAIN KNOWLEDGE (science, mechanics, theories, entities).\n"
# #                             "2. IGNORE publication metadata (publishers, copyrights, ISBNs, author names, editions).\n"
# #                             "3. Maintain logical relationships. Concepts must belong to their parent section.\n"
# #                             "4. Avoid duplicate concepts. Connect entities based solely on scientific reality.\n"
# #                             "5. If a section is purely administrative, return empty arrays."
# #                         )
# #                     },
# #                     {
# #                         "role": "user", 
# #                         "content": f"Extract domain concepts and relationships from this section:\n\n{section_payload}"
# #                     }
# #                 ],
# #                 response_format=KnowledgeExtractionPayload,
# #                 temperature=0.0  # Zero temperature for maximum factual consistency
# #             )

# #             result = completion.choices[0].message.parsed
# #             extracted = {"concepts": [], "relationships": [], "scientific_rules": [], "procedures": []}

# #             if result:
# #                 # Inject hierarchy context directly into the extracted nodes
# #                 for c in result.concepts:
# #                     c_dict = c.model_dump()
# #                     c_dict["hierarchy_context"] = path_str
# #                     c_dict["source_page"] = first_page
# #                     extracted["concepts"].append(c_dict)

# #                 extracted["relationships"] = [r.model_dump() for r in result.relationships]
# #                 extracted["scientific_rules"] = [sr.model_dump() for sr in result.scientific_rules]
# #                 extracted["procedures"] = [p.model_dump() for p in result.procedures]
                
# #             return extracted

# #         except Exception as e:
# #             logger.error(f"LLM extraction error on chunk {chunk_id}: {str(e)}")
# #             return {"concepts": [], "relationships": [], "scientific_rules": [], "procedures": []}

# #     def _deduplicate_and_merge_concepts(self, raw_concepts: List[Dict]) -> List[Dict]:
# #         """Merges duplicate concepts, combining their synonyms and keywords."""
# #         merged = {}
# #         for c in raw_concepts:
# #             key = c["canonical_name"].strip().lower()
# #             if key in merged:
# #                 # Merge lists and remove duplicates
# #                 merged[key]["synonyms"] = list(set(merged[key].get("synonyms", []) + c.get("synonyms", [])))
# #                 merged[key]["keywords"] = list(set(merged[key].get("keywords", []) + c.get("keywords", [])))
# #                 # Combine hierarchy contexts if they differ
# #                 if c.get("hierarchy_context") and c["hierarchy_context"] not in merged[key].get("hierarchy_context", ""):
# #                     merged[key]["hierarchy_context"] += f" | {c['hierarchy_context']}"
# #             else:
# #                 merged[key] = c
                
# #         return list(merged.values())

# #     async def extract_knowledge(self, document_id: str) -> dict:
# #         processed_base = self.processed_dir / document_id
# #         tree_path = processed_base / "document_tree.json"
# #         metadata_path = self.raw_dir / document_id / "metadata.json"

# #         if not tree_path.exists():
# #             raise DocumentNotFoundError(f"Document structure tree for {document_id} not found.")

# #         try:
# #             logger.info(f"Starting highly-contextual Semantic Extraction for {document_id}")
            
# #             with open(tree_path, "r", encoding="utf-8") as f:
# #                 document_tree = json.load(f)

# #             # 1. Group elements by Semantic Section (skipping front-matter)
# #             sections_map = {}
# #             ignored_page_types = ["cover", "title", "copyright", "toc", "preface", "acknowledgements"]
            
# #             for page in document_tree.get("pages", []):
# #                 if page.get("page_type") in ignored_page_types:
# #                     continue
                    
# #                 for el in page.get("elements", []):
# #                     # Group by semantic chunk. If missing, fallback to page-level chunk.
# #                     chunk_id = el.get("semantic_chunk_id") or f"page_chunk_{page.get('page_number')}"
                    
# #                     if chunk_id not in sections_map:
# #                         sections_map[chunk_id] = {"path": el.get("section_path", []), "elements": []}
                    
# #                     sections_map[chunk_id]["elements"].append(el)

# #             # 2. Process Sections Concurrently with Semaphore limits
# #             sem = asyncio.Semaphore(self.max_concurrent_requests)
            
# #             async def bounded_process(c_id, data):
# #                 async with sem:
# #                     return await self._process_semantic_section(c_id, data)

# #             tasks = [bounded_process(cid, data) for cid, data in sections_map.items()]
# #             batch_results = await asyncio.gather(*tasks)

# #             # 3. Aggregate Results
# #             raw_concepts = []
# #             master_knowledge = {
# #                 "document_id": document_id,
# #                 "relationships": [],
# #                 "scientific_rules": [],
# #                 "procedures": []
# #             }

# #             for res in batch_results:
# #                 raw_concepts.extend(res.get("concepts", []))
# #                 master_knowledge["relationships"].extend(res.get("relationships", []))
# #                 master_knowledge["scientific_rules"].extend(res.get("scientific_rules", []))
# #                 master_knowledge["procedures"].extend(res.get("procedures", []))

# #             # 4. Deduplicate Concepts
# #             master_knowledge["concepts"] = self._deduplicate_and_merge_concepts(raw_concepts)

# #             # 5. Save Artifact
# #             extracted_knowledge_path = processed_base / "extracted_knowledge.json"
# #             with open(extracted_knowledge_path, "w", encoding="utf-8") as kf:
# #                 json.dump(master_knowledge, kf, indent=4)

# #             # 6. Update Pipeline Metadata
# #             if metadata_path.exists():
# #                 with open(metadata_path, "r+", encoding="utf-8") as mf:
# #                     meta_data = json.load(mf)
# #                     meta_data["pipeline_status"] = "KNOWLEDGE_EXTRACTED"
# #                     meta_data["next_step"] = f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
# #                     mf.seek(0)
# #                     json.dump(meta_data, mf, indent=2)
# #                     mf.truncate()

# #             logger.info(f"Extraction complete for {document_id}. "
# #                         f"Concepts: {len(master_knowledge['concepts'])} (Deduplicated), "
# #                         f"Relationships: {len(master_knowledge['relationships'])}")

# #             return {
# #                 "document_id": document_id,
# #                 "pipeline_status": "KNOWLEDGE_EXTRACTED",
# #                 "extracted_stats": {
# #                     "concepts_extracted": len(master_knowledge["concepts"]),
# #                     "relationships_extracted": len(master_knowledge["relationships"])
# #                 },
# #                 "knowledge_artifact_path": str(extracted_knowledge_path.relative_to(settings.BASE_DIR))
# #             }

# #         except Exception as e:
# #             logger.error(f"Knowledge extraction failed for {document_id}: {str(e)}", exc_info=True)
# #             raise StorageError(f"Knowledge extraction failed: {str(e)}")





# # import json
# # import asyncio
# # import re
# # import secrets
# # from difflib import SequenceMatcher
# # from typing import Dict, Any, List, Tuple, Set, Optional
# # from pydantic import BaseModel, Field
# # from openai import AsyncOpenAI

# # # Graceful token counting
# # try:
# #     import tiktoken
# #     _TOKENIZER = tiktoken.get_encoding("cl100k_base")
# #     def count_tokens(text: str) -> int:
# #         return len(_TOKENIZER.encode(text))
# # except ImportError:
# #     def count_tokens(text: str) -> int:
# #         return len(text) // 4

# # from app.core.config import settings
# # from app.core.exceptions import DocumentNotFoundError, ProcessingError, StorageError
# # from app.core.logger import logger

# # ###############################################################################
# # # TAGTASTE EXTRACTION SCHEMAS (Dynamic Validation)
# # ###############################################################################

# # class ConceptTerm(BaseModel):
# #     term: str
# #     term_type: str = Field(description="Must be one of: canonical, synonym, dataset_phrase, user_phrase")

# # class RawExtractedConcept(BaseModel):
# #     type_key: str = Field(description="Must match exactly one of the dynamically provided Concept DB type_keys.")
# #     canonical_name: str
# #     definition: str
# #     concept_terms: List[ConceptTerm]
# #     type_data: Dict[str, Any] = Field(description="Structured JSON matching the type's field schema.")
# #     ai_confidence: float
# #     ai_reasoning: str = Field(description="Brief justification for why this concept should be added to the Concept DB.")

# # class RawExtractedRelationship(BaseModel):
# #     source_concept: str
# #     target_concept: str
# #     relationship_type: str = Field(description="Must match exactly one of the dynamically provided Concept DB relationship labels.")
# #     strength: float = Field(default=1.0)

# # class TagTasteExtractionPayload(BaseModel):
# #     concepts: List[RawExtractedConcept]
# #     relationships: List[RawExtractedRelationship]

# # ###############################################################################
# # # KNOWLEDGE SERVICE (TAGTASTE CONCEPT PIPELINE)
# # ###############################################################################

# # class KnowledgeService:
# #     def __init__(self, db_service=None):
# #         self.raw_dir = settings.STORAGE_RAW_DIR
# #         self.processed_dir = settings.STORAGE_PROCESSED_DIR
        
# #         self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
# #         self.model_name = "gpt-4o-mini"
# #         self.max_concurrent_requests = getattr(settings, "MAX_CONCURRENT_EXTRACTIONS", 5)
# #         self.max_tokens_per_prompt = 7000  
# #         self.overlap_elements = 3

# #         # In a real FastAPI app, this is injected. Used here to represent Concept DB lookup.
# #         self.db_service = db_service 

# #     ###########################################################################
# #     # STAGE 1: LOGICAL ROUTING & DYNAMIC POLICY LOADING
# #     ###########################################################################

# #     async def _fetch_active_db_policies(self) -> Dict[str, List[str]]:
# #         """
# #         Fetches the live Concept DB schema to prevent hardcoding. 
# #         In production, this calls self.db_service.get_active_types().
# #         """
# #         # Fallback payload representing the live 2026-05-08 TagTaste Concept DB state
# #         return {
# #             "type_keys": [
# #                 # Sensory Substrate
# #                 "descriptor", "sensory_attribute", "sensory_scale", "family", "axis", "modality", "food_science",
# #                 # Routing & Policy Layer
# #                 "intent_group", "sql_query_pattern", "analysis_recipe", "recipe_step", "classifier_prompt", 
# #                 "governance_rule", "answer_example", "category_knowledge", "alignment_gate", "domain", "metric"
# #             ],
# #             "relationship_types": [
# #                 "is_child_of", "causes", "measured_by", "described_by", "influences", "related_to", "part_of",
# #                 "categorized_as", "applies_to", "is_example_of", "uses_sql", "composes_from", "pulls_from",
# #                 "measured_on", "gated_by", "default_prompt", "default_shape", "triggered_by", "benchmarked_by",
# #                 "threshold_for", "uses_weights", "column_in", "renders_as", "evaluated_against"
# #             ]
# #         }

# #     def _apply_dynamic_hierarchy(self, elements: List[Dict]) -> List[Dict]:
# #         active_h1, active_h2, active_h3 = "Unknown Chapter", "", ""
# #         for el in elements:
# #             if el.get("type") == "heading":
# #                 lvl = el.get("heading_level", 0)
# #                 text = el.get("text", "").strip()
# #                 if lvl == 1:
# #                     active_h1 = text
# #                     active_h2, active_h3 = "", ""
# #                 elif lvl == 2:
# #                     active_h2 = text
# #                     active_h3 = ""
# #                 elif lvl >= 3:
# #                     active_h3 = text
# #             el["logical_chapter"] = active_h1
# #             el["logical_section"] = active_h2
# #             el["logical_subsection"] = active_h3
# #         return elements

# #     def _build_logical_units(self, elements: List[Dict], book_title: str) -> List[Dict]:
# #         elements = self._apply_dynamic_hierarchy(elements)
# #         logical_units = []

# #         # Group by Chapter
# #         chapters = {}
# #         for el in elements:
# #             ch = el["logical_chapter"]
# #             if ch not in chapters: chapters[ch] = []
# #             chapters[ch].append(el)

# #         for ch_title, ch_elements in chapters.items():
# #             if sum(count_tokens(e.get("text", "")) for e in ch_elements) <= self.max_tokens_per_prompt:
# #                 logical_units.append({"book_title": book_title, "unit_type": "chapter", "elements": ch_elements})
# #                 continue
            
# #             # Group by Section
# #             sections = {}
# #             for el in ch_elements:
# #                 sec = el["logical_section"]
# #                 if sec not in sections: sections[sec] = []
# #                 sections[sec].append(el)
                
# #             for sec_title, sec_elements in sections.items():
# #                 if sum(count_tokens(e.get("text", "")) for e in sec_elements) <= self.max_tokens_per_prompt:
# #                     logical_units.append({"book_title": book_title, "unit_type": "section", "elements": sec_elements})
# #                     continue
                
# #                 logical_units.extend(self._fallback_linear_split(sec_elements, book_title))

# #         return logical_units

# #     def _fallback_linear_split(self, elements: List[Dict], book_title: str) -> List[Dict]:
# #         chunks = []
# #         current_chunk = []
# #         current_tokens = 0

# #         for i, el in enumerate(elements):
# #             el_text = el.get("text", "")
# #             el_tokens = count_tokens(el_text) + 20
            
# #             current_chunk.append(el)
# #             current_tokens += el_tokens

# #             is_boundary = el.get("type") in ["paragraph", "heading"]
# #             if current_tokens > self.max_tokens_per_prompt and is_boundary and i < len(elements) - 1:
# #                 chunks.append({"book_title": book_title, "unit_type": "chunk", "elements": current_chunk})
# #                 overlap = current_chunk[-self.overlap_elements:] if len(current_chunk) > self.overlap_elements else current_chunk
# #                 current_chunk = overlap.copy()
# #                 current_tokens = sum(count_tokens(e.get("text", "")) + 20 for e in current_chunk)

# #         if current_chunk:
# #             chunks.append({"book_title": book_title, "unit_type": "chunk", "elements": current_chunk})
# #         return chunks

# #     def _build_json_payload(self, unit: Dict[str, Any], memory: Set[str]) -> str:
# #         first_el = unit["elements"][0]
# #         pages = sorted(list(set([e.get("page_number") for e in unit["elements"] if e.get("page_number")])))
        
# #         content_blocks = [{"type": el.get("type", "paragraph"), "text": el.get("text", "").strip()} 
# #                           for el in unit["elements"] if "text" in el]

# #         payload = {
# #             "document_context": {
# #                 "book_title": unit["book_title"],
# #                 "chapter": first_el.get("logical_chapter", ""),
# #                 "section": first_el.get("logical_section", ""),
# #                 "subsection": first_el.get("logical_subsection", ""),
# #                 "pages": pages
# #             },
# #             "concept_memory": list(memory)[-100:], 
# #             "content": content_blocks
# #         }
# #         return json.dumps(payload, ensure_ascii=False)

# #     ###########################################################################
# #     # STAGE 2: DUAL-LAYER LLM EXTRACTION (Sensory + Policy)
# #     ###########################################################################

# #     async def _process_logical_unit(self, unit_id: str, unit: Dict[str, Any], memory: Set[str], policies: Dict[str, List[str]]) -> Dict[str, List[Any]]:
# #         json_payload = self._build_json_payload(unit, memory)
        
# #         if len(json_payload.strip()) < 150:
# #             return {"concepts": [], "relationships": []}

# #         try:
# #             logger.debug(f"Extracting TagTaste proposals for {unit_id}")
            
# #             completion = await self.client.beta.chat.completions.parse(
# #                 model=self.model_name,
# #                 messages=[
# #                     {
# #                         "role": "system", 
# #                         "content": (
# #                             "You are the TagTaste Concept Proposal Engine.\n\n"
# #                             "DUAL-LAYER ARCHITECTURE RULES:\n"
# #                             "1. SENSORY SUBSTRATE: Extract scientific entities mapping to: sensory_attribute, descriptor, sensory_scale, family, axis, modality.\n"
# #                             "2. POLICY & ROUTING LAYER: Extract pipeline mechanics mapping to: intent_group, analysis_recipe, sql_query_pattern, governance_rule.\n\n"
# #                             "DATABASE CONSTRAINTS:\n"
# #                             f"- VALID TYPE_KEYS: {policies['type_keys']}\n"
# #                             f"- VALID RELATIONSHIPS: {policies['relationship_types']}\n"
# #                             "- hierarchy: Identify TagTaste hierarchy (Axis -> Family -> Attribute -> Descriptor) or (Recipe -> IG -> QP).\n"
# #                             "- type_data: Extract structured JSON fields for the concept type (e.g., 'scale_points' for scales, 'measurement_type' for attributes).\n"
# #                             "- concept_terms: Supply 'dataset_phrase' and 'user_phrase' variants to enable matching.\n\n"
# #                             "DOCUMENT MEMORY:\n"
# #                             "Check 'concept_memory'. Reuse exact canonical names for existing concepts."
# #                         )
# #                     },
# #                     {
# #                         "role": "user", 
# #                         "content": json_payload
# #                     }
# #                 ],
# #                 response_format=TagTasteExtractionPayload,
# #                 temperature=0.0
# #             )

# #             result = completion.choices[0].message.parsed
# #             extracted = {"concepts": [], "relationships": []}

# #             if result:
# #                 for c in result.concepts:
# #                     c_dict = c.model_dump()
# #                     extracted["concepts"].append(c_dict)
# #                     memory.add(c_dict["canonical_name"])

# #                 for r in result.relationships:
# #                     extracted["relationships"].append(r.model_dump())
                
# #             return extracted

# #         except Exception as e:
# #             logger.error(f"LLM extraction error on unit {unit_id}: {str(e)}")
# #             return {"concepts": [], "relationships": []}

# #     ###########################################################################
# #     # STAGE 3: CONCEPT LOADER RESOLUTION & PROPOSAL GENERATION
# #     ###########################################################################

# #     def _determine_qdrant_group(self, type_key: str) -> str:
# #         """Determines vector sync strategy based on the TagTaste script specs."""
# #         group_a = {"descriptor", "sensory_attribute", "sensory_scale", "family", "axis", "modality", "analysis_recipe", "sql_query_pattern"}
# #         group_b = {"intent_group", "guardrail_rule", "domain"}
# #         group_c_d = {"classifier_prompt", "persona", "ar_question_slot"}
        
# #         if type_key in group_a: return "Group A (concepts collection)"
# #         if type_key in group_b: return "Group B (concept_terms_unified)"
# #         if type_key in group_c_d: return "Group C/D (No Vector)"
# #         return "Unknown"

# #     async def _resolve_with_concept_db(self, raw_concepts: List[Dict]) -> Tuple[List[Dict], List[Dict], Dict[str, str]]:
# #         """
# #         Queries the TagTaste Concept DB. 
# #         If found: Reuses exact concept_uid.
# #         If missing: Generates a payload strictly matching the `concept_proposals` table.
# #         """
# #         resolved_concepts = []
# #         pending_proposals = []
# #         uid_map = {} # Maps canonical_name -> resolved_uid (for relationship mapping)

# #         for c in raw_concepts:
# #             canonical = c["canonical_name"].strip()
# #             type_key = c["type_key"].strip()
            
# #             # In Production: existing_uid = await self.db_service.find_concept(canonical, type_key)
# #             existing_uid = None  # Simulated missing concept

# #             if existing_uid:
# #                 # 1. Reuse existing concept
# #                 resolved_concepts.append({"concept_uid": existing_uid, "canonical_name": canonical})
# #                 uid_map[canonical.lower()] = existing_uid
# #             else:
# #                 # 2. Generate Proposal matching DB schema exactly
# #                 proposal_uid = f"CP_{secrets.token_hex(4)}"
# #                 proposal = {
# #                     "proposal_uid": proposal_uid,
# #                     "proposed_type": type_key,
# #                     "proposed_name": canonical,
# #                     "proposed_name_normalized": re.sub(r'[^a-z0-9]', '', canonical.lower()),
# #                     "proposed_definition": c["definition"],
# #                     "proposed_data": c["type_data"],
# #                     "proposed_terms": c["concept_terms"],
# #                     "ai_confidence": c["ai_confidence"],
# #                     "ai_reasoning": c["ai_reasoning"],
# #                     "status": "pending",
# #                     "priority": "normal",
# #                     "requires_expert": type_key in ["sql_query_pattern", "intent_group"], # Policy requires expert
# #                     "created_by": "ai_extractor_pipeline",
# #                     "qdrant_target": self._determine_qdrant_group(type_key)
# #                 }
# #                 pending_proposals.append(proposal)
# #                 uid_map[canonical.lower()] = proposal_uid

# #         return resolved_concepts, pending_proposals, uid_map

# #     def _resolve_relationships(self, raw_rels: List[Dict], uid_map: Dict[str, str], valid_types: List[str]) -> List[Dict]:
# #         """Maps relationships to exact concept/proposal UIDs and strips invalid edges."""
# #         valid_rels = []
# #         seen = set()

# #         for r in raw_rels:
# #             src_key = r["source_concept"].strip().lower()
# #             tgt_key = r["target_concept"].strip().lower()
# #             rel_type = r["relationship_type"]

# #             # Must use TagTaste valid relationship type
# #             if rel_type not in valid_types:
# #                 continue

# #             src_uid = uid_map.get(src_key)
# #             tgt_uid = uid_map.get(tgt_key)

# #             if src_uid and tgt_uid and src_uid != tgt_uid:
# #                 sig = f"{src_uid}::{rel_type}::{tgt_uid}"
# #                 if sig not in seen:
# #                     valid_rels.append({
# #                         "source_uid": src_uid,
# #                         "target_uid": tgt_uid,
# #                         "relationship_type": rel_type,
# #                         "strength": r.get("strength", 1.0)
# #                     })
# #                     seen.add(sig)

# #         return valid_rels

# #     ###########################################################################
# #     # MASTER EXECUTION PIPELINE
# #     ###########################################################################

# #     async def extract_knowledge(self, document_id: str) -> Dict[str, Any]:
# #         processed_base = self.processed_dir / document_id
# #         tree_path = processed_base / "document_tree.json"

# #         if not tree_path.exists():
# #             raise DocumentNotFoundError(f"Structure tree missing for {document_id}")

# #         try:
# #             logger.info(f"Starting TagTaste Concept DB Extraction for {document_id}")
            
# #             with open(tree_path, "r", encoding="utf-8") as f:
# #                 document_tree = json.load(f)

# #             # 1. Fetch Dynamic Policy from TagTaste Concept DB
# #             db_policies = await self._fetch_active_db_policies()

# #             # 2. Build Logical Routing Units
# #             ignored_pages = {"cover", "title", "copyright", "toc", "preface"}
# #             elements = [el for p in document_tree.get("pages", []) if p.get("page_type") not in ignored_pages for el in p.get("elements", [])]
# #             logical_units = self._build_logical_units(elements, document_tree.get("document_metadata", {}).get("book_title", ""))

# #             # 3. Process LLM Extraction
# #             global_memory = set()
# #             raw_concepts, raw_relationships = [], []
            
# #             sem = asyncio.Semaphore(self.max_concurrent_requests)
# #             async def bounded_process(u_idx: int, data: Dict[str, Any]):
# #                 async with sem:
# #                     return await self._process_logical_unit(f"unit_{u_idx}", data, global_memory, db_policies)

# #             tasks = [bounded_process(i, unit) for i, unit in enumerate(logical_units)]
# #             for res in await asyncio.gather(*tasks):
# #                 raw_concepts.extend(res.get("concepts", []))
# #                 raw_relationships.extend(res.get("relationships", []))

# #             # 4. ConceptLoader: Resolve Existing vs. Proposals
# #             resolved_concepts, pending_proposals, uid_map = await self._resolve_with_concept_db(raw_concepts)
            
# #             # 5. Relationship DB Mapping
# #             valid_relationships = self._resolve_relationships(raw_relationships, uid_map, db_policies["relationship_types"])

# #             # 6. Save DB-Ready Artifact
# #             db_artifact = {
# #                 "document_id": document_id,
# #                 "resolved_concepts": resolved_concepts,
# #                 "concept_proposals": pending_proposals,
# #                 "concept_relationships": valid_relationships
# #             }

# #             extracted_knowledge_path = processed_base / "extracted_knowledge.json"
# #             with open(extracted_knowledge_path, "w", encoding="utf-8") as kf:
# #                 json.dump(db_artifact, kf, indent=4)

# #             logger.info(f"TagTaste Pipeline complete: {len(resolved_concepts)} Resolved, {len(pending_proposals)} Proposals, {len(valid_relationships)} Relationships.")

# #             return {
# #                 "document_id": document_id,
# #                 "pipeline_status": "KNOWLEDGE_EXTRACTED",
# #                 "extracted_stats": {
# #                     "resolved_concepts": len(resolved_concepts),
# #                     "pending_proposals": len(pending_proposals),
# #                     "relationships": len(valid_relationships)
# #                 }
# #             }

# #         except Exception as e:
# #             logger.error(f"Knowledge extraction failed: {str(e)}", exc_info=True)
# #             raise StorageError(f"Knowledge extraction failed: {str(e)}")

            






# # import json
# # import asyncio
# # import re
# # from typing import Dict, Any, List, Tuple
# # from openai import AsyncOpenAI

# # # Graceful token counting (TikToken preferred, character heuristic fallback)
# # try:
# #     import tiktoken
# #     _TOKENIZER = tiktoken.get_encoding("cl100k_base")
# #     def count_tokens(text: str) -> int:
# #         return len(_TOKENIZER.encode(text))
# # except ImportError:
# #     def count_tokens(text: str) -> int:
# #         return len(text) // 4

# # from app.core.config import settings
# # from app.core.exceptions import DocumentNotFoundError, ProcessingError, StorageError
# # from app.core.logger import logger
# # from app.models.knowledge import KnowledgeExtractionPayload


# # class KnowledgeService:
# #     def __init__(self):
# #         self.raw_dir = settings.STORAGE_RAW_DIR
# #         self.processed_dir = settings.STORAGE_PROCESSED_DIR
        
# #         self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
# #         self.model_name = "gpt-4o-mini"
        
# #         self.max_concurrent_requests = getattr(settings, "MAX_CONCURRENT_EXTRACTIONS", 5)
# #         self.max_tokens_per_chunk = 6000  # Conservative limit to leave room for LLM JSON output
# #         self.overlap_elements = 3         # Applied ONLY during fallback chunking

# #         # Controlled Vocabulary for Enterprise Graph Consistency
# #         self.ontology_categories = [
# #             "Entity", "Method", "Theory", "Process", "Material", 
# #             "Chemical", "Instrument", "Organization", "Measurement", "Property"
# #         ]

# #     ###########################################################################
# #     # STAGE 1: HIERARCHY-DRIVEN DOCUMENT SPLITTING
# #     ###########################################################################

# #     def _collect_section_elements(self, document_tree: Dict[str, Any]) -> List[Dict[str, Any]]:
# #         """Traverses document_tree, ignores front-matter pages, returns pure body elements."""
# #         ignored_page_types = {"cover", "title", "copyright", "toc", "preface", "acknowledgements"}
# #         annotated_elements = []

# #         for page in document_tree.get("pages", []):
# #             if page.get("page_type") in ignored_page_types:
# #                 continue
# #             for el in page.get("elements", []):
# #                 annotated_elements.append(el)

# #         return annotated_elements

# #     def _hierarchical_split(self, elements: List[Dict], book_title: str, depth: int) -> List[Dict]:
# #         """
# #         Recursively attempts to fit the largest possible logical document unit 
# #         (Book -> Chapter -> Section) into the LLM context window.
# #         """
# #         if not elements:
# #             return []

# #         # Check total token size of current logical block
# #         text_content = " ".join([e.get("text", "") for e in elements])
# #         total_tokens = count_tokens(text_content)

# #         # If the entire chapter/section fits, return it as one unified payload
# #         if total_tokens <= self.max_tokens_per_chunk:
# #             return [{"book_title": book_title, "elements": elements}]

# #         # If it exceeds limits, group elements by their sub-hierarchy at current depth
# #         groups = []
# #         group_keys = []
# #         current_key = None
# #         current_group = []

# #         for el in elements:
# #             path = el.get("section_path", [])
# #             key = path[depth] if depth < len(path) else ""
            
# #             if key != current_key:
# #                 if current_group:
# #                     groups.append(current_group)
# #                     group_keys.append(current_key)
# #                 current_key = key
# #                 current_group = []
# #             current_group.append(el)
            
# #         if current_group:
# #             groups.append(current_group)
# #             group_keys.append(current_key)

# #         # If all elements belong to the exact same lowest-level subsection but STILL 
# #         # exceed token limits, we are forced to use overlap chunking.
# #         if len(groups) == 1:
# #             return self._fallback_linear_split(elements, book_title)

# #         # Otherwise, recurse deeper into the hierarchy
# #         chunks = []
# #         for grp in groups:
# #             chunks.extend(self._hierarchical_split(grp, book_title, depth + 1))

# #         return chunks

# #     def _fallback_linear_split(self, elements: List[Dict], book_title: str) -> List[Dict]:
# #         """Last resort: Splits an oversized subsection using a sliding overlap window."""
# #         chunks = []
# #         current_chunk = []
# #         current_tokens = 0

# #         for i, el in enumerate(elements):
# #             el_text = el.get("text", "")
# #             el_tokens = count_tokens(el_text) + 15  # Buffer for formatting overhead
            
# #             current_chunk.append(el)
# #             current_tokens += el_tokens

# #             # Split only at natural boundaries (never inside tables or captions)
# #             is_boundary = el.get("type") in ["paragraph", "heading", "image", "table"]
            
# #             if current_tokens > self.max_tokens_per_chunk and is_boundary and i < len(elements) - 1:
# #                 chunks.append({"book_title": book_title, "elements": current_chunk})
                
# #                 # Create overlapping context to prevent breaking relationships
# #                 overlap = current_chunk[-self.overlap_elements:] if len(current_chunk) > self.overlap_elements else current_chunk
# #                 current_chunk = overlap.copy()
# #                 current_tokens = sum(count_tokens(e.get("text", "")) + 15 for e in current_chunk)

# #         if current_chunk:
# #             chunks.append({"book_title": book_title, "elements": current_chunk})

# #         return chunks

# #     def _format_logical_payload(self, chunk: Dict[str, Any]) -> str:
# #         """Constructs prompt payload injecting strict Parent Hierarchy above content blocks."""
# #         book_title = chunk["book_title"]
# #         pages = sorted(list(set([e.get("page_number") for e in chunk["elements"] if e.get("page_number")])))
# #         page_str = f"Pages: {pages[0]} - {pages[-1]}" if len(pages) > 1 else f"Page: {pages[0]}" if pages else ""

# #         lines = [
# #             "=== DOCUMENT CONTEXT ===",
# #             f"Book: {book_title}",
# #             f"{page_str}",
# #             "\n=== CONTENT TO EXTRACT ==="
# #         ]

# #         current_path = None
# #         for el in chunk["elements"]:
# #             path = tuple(el.get("section_path", []))
            
# #             # Dynamically inject hierarchy whenever the section changes
# #             if path != current_path:
# #                 path_str = " > ".join(path) if path else "General Content"
# #                 lines.append(f"\n--- HIERARCHY: {path_str} ---")
# #                 current_path = path

# #             t = el.get("type", "paragraph")
# #             if t in ["heading", "paragraph", "caption", "list_item", "equation", "cross_ref"]:
# #                 text_content = el.get("text", "").strip()
# #                 if text_content:
# #                     lines.append(f"[{t.upper()}] {text_content}")
# #             elif t == "table":
# #                 lines.append(f"[TABLE index_{el.get('table_index', '0')}]")
# #                 for row in el.get("rows", []):
# #                     row_content = " | ".join([str(cell or "").strip() for cell in row])
# #                     lines.append(f"| {row_content} |")
# #             elif t in ["image", "figure", "diagram", "photo"]:
# #                 lines.append(f"[FIGURE ref={el.get('element_id', 'unknown')}]")

# #         return "\n".join(lines)

# #     ###########################################################################
# #     # STAGE 2: CONTEXT-AWARE LLM EXTRACTION
# #     ###########################################################################

# #     async def _process_logical_unit(self, chunk_id: str, chunk: Dict[str, Any]) -> Dict[str, List[Any]]:
# #         section_payload = self._format_logical_payload(chunk)
# #         first_page = chunk["elements"][0].get("page_number") if chunk["elements"] else None

# #         if len(section_payload.strip()) < 150:
# #             return {"concepts": [], "relationships": [], "scientific_rules": [], "procedures": []}

# #         try:
# #             logger.debug(f"Extracting knowledge graph for logical unit {chunk_id}")
            
# #             completion = await self.client.beta.chat.completions.parse(
# #                 model=self.model_name,
# #                 messages=[
# #                     {
# #                         "role": "system", 
# #                         "content": (
# #                             "You are an expert scientific Knowledge Graph extraction engine.\n"
# #                             "STRICT EXTRACTION DIRECTIVES:\n"
# #                             "1. EXTRACT ONLY DOMAIN KNOWLEDGE (scientific concepts, methodologies, formulas, mechanisms).\n"
# #                             "2. ONTOLOGY ENFORCEMENT: The 'category' MUST be one of: " f"{self.ontology_categories}\n"
# #                             "3. IGNORE PUBLICATION METADATA (authors, publishers, ISBNs, copyrights, page headers).\n"
# #                             "4. HIERARCHY AWARENESS: You will receive content grouped by logical document structure. Use the '--- HIERARCHY: ... ---' markers to attach the correct parent context to every concept.\n"
# #                             "5. PREVENT KEYWORD EXPLOSION: Limit to maximum 5 highly normalized keywords per concept."
# #                         )
# #                     },
# #                     {
# #                         "role": "user", 
# #                         "content": f"Extract domain knowledge from this logical document unit:\n\n{section_payload}"
# #                     }
# #                 ],
# #                 response_format=KnowledgeExtractionPayload,
# #                 temperature=0.0
# #             )

# #             result = completion.choices[0].message.parsed
# #             extracted = {"concepts": [], "relationships": [], "scientific_rules": [], "procedures": []}

# #             if result:
# #                 for c in result.concepts:
# #                     c_dict = c.model_dump()
# #                     # Ensure hierarchy context defaults gracefully if LLM missed it
# #                     c_dict["hierarchy_context"] = c_dict.get("hierarchy_context") or "Extracted Content"
# #                     c_dict["source_page"] = first_page
# #                     extracted["concepts"].append(c_dict)

# #                 extracted["relationships"] = [r.model_dump() for r in result.relationships]
# #                 extracted["scientific_rules"] = [sr.model_dump() for sr in result.scientific_rules]
# #                 extracted["procedures"] = [p.model_dump() for p in result.procedures]
                
# #             return extracted

# #         except Exception as e:
# #             logger.error(f"LLM extraction error on logical unit {chunk_id}: {str(e)}")
# #             return {"concepts": [], "relationships": [], "scientific_rules": [], "procedures": []}

# #     ###########################################################################
# #     # STAGE 3: GLOBAL DEDUPLICATION & GRAPH STITCHING
# #     ###########################################################################

# #     def _normalize_key(self, name: str) -> str:
# #         """Stems plurals and normalizes strings to reliably merge concepts."""
# #         key = re.sub(r'[^a-z0-9]', '', name.lower())
# #         if key.endswith('s') and not key.endswith('ss') and len(key) > 3:
# #             key = key[:-1]
# #         return key

# #     def _stitch_global_graph(
# #         self, raw_concepts: List[Dict[str, Any]], raw_relationships: List[Dict[str, Any]]
# #     ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
# #         """
# #         Second-pass Graph Stitching:
# #         1. Ontology-aware concept merging via stemmed canonical keys.
# #         2. Filters out rogue metadata nodes hallucinated by the LLM.
# #         3. Validates relationships: Maps edges strictly to surviving nodes and removes duplicate loops.
# #         """
# #         merged_concepts = {}
# #         metadata_keywords = {"press", "isbn", "copyright", "edition", "publisher", "inc", "ltd", "author"}

# #         # Pass 1: Deduplicate Concepts globally across all logical units
# #         for c in raw_concepts:
# #             c_name = c["canonical_name"].strip()
# #             key = self._normalize_key(c_name)

# #             if any(bad in key for bad in metadata_keywords):
# #                 continue

# #             if key in merged_concepts:
# #                 merged_concepts[key]["synonyms"] = list(set(merged_concepts[key].get("synonyms", []) + c.get("synonyms", [])))
# #                 merged_kws = list(set(merged_concepts[key].get("keywords", []) + c.get("keywords", [])))
# #                 merged_concepts[key]["keywords"] = merged_kws[:5]
                
# #                 if c.get("hierarchy_context") and c["hierarchy_context"] not in merged_concepts[key].get("hierarchy_context", ""):
# #                     merged_concepts[key]["hierarchy_context"] += f" | {c['hierarchy_context']}"
# #             else:
# #                 c["canonical_name"] = c_name
# #                 c["keywords"] = list(set(c.get("keywords", [])))[:5]
# #                 merged_concepts[key] = c

# #         # Pass 2: Remap & Validate Relationships
# #         valid_keys = set(merged_concepts.keys())
# #         clean_relationships = []
# #         seen_relationships = set()

# #         for r in raw_relationships:
# #             src_key = self._normalize_key(r["source_concept"].strip())
# #             tgt_key = self._normalize_key(r["target_concept"].strip())

# #             if src_key in valid_keys and tgt_key in valid_keys:
# #                 if src_key == tgt_key:
# #                     continue  

# #                 r["source_concept"] = merged_concepts[src_key]["canonical_name"]
# #                 r["target_concept"] = merged_concepts[tgt_key]["canonical_name"]

# #                 rel_signature = f"{src_key}:::{r['relationship_type']}::{tgt_key}"
# #                 if rel_signature not in seen_relationships:
# #                     clean_relationships.append(r)
# #                     seen_relationships.add(rel_signature)

# #         return list(merged_concepts.values()), clean_relationships

# #     ###########################################################################
# #     # MASTER EXECUTION PIPELINE
# #     ###########################################################################

# #     async def extract_knowledge(self, document_id: str) -> Dict[str, Any]:
# #         processed_base = self.processed_dir / document_id
# #         tree_path = processed_base / "document_tree.json"
# #         metadata_path = self.raw_dir / document_id / "metadata.json"

# #         if not tree_path.exists():
# #             raise DocumentNotFoundError(f"Document structure tree for {document_id} not found.")

# #         try:
# #             logger.info(f"Starting Hierarchical Semantic Extraction for {document_id}")
            
# #             with open(tree_path, "r", encoding="utf-8") as f:
# #                 document_tree = json.load(f)

# #             book_title = document_tree.get("document_metadata", {}).get("book_title") or "Scientific Text"
# #             elements = self._collect_section_elements(document_tree)

# #             # 1. Build Token-Aware Logical Units (Book -> Chapter -> Section)
# #             logical_units = self._hierarchical_split(elements, book_title, depth=0)

# #             # 2. Process Logical Units Concurrently
# #             sem = asyncio.Semaphore(self.max_concurrent_requests)
            
# #             async def bounded_process(u_idx: int, data: Dict[str, Any]):
# #                 async with sem:
# #                     return await self._process_logical_unit(f"unit_{u_idx}", data)

# #             tasks = [bounded_process(i, unit) for i, unit in enumerate(logical_units)]
# #             batch_results = await asyncio.gather(*tasks)

# #             # 3. Collect Raw Outputs
# #             raw_concepts, raw_relationships = [], []
# #             master_knowledge = {
# #                 "document_id": document_id,
# #                 "scientific_rules": [],
# #                 "procedures": []
# #             }

# #             for res in batch_results:
# #                 raw_concepts.extend(res.get("concepts", []))
# #                 raw_relationships.extend(res.get("relationships", []))
# #                 master_knowledge["scientific_rules"].extend(res.get("scientific_rules", []))
# #                 master_knowledge["procedures"].extend(res.get("procedures", []))

# #             # 4. Global Graph Stitching & Validation
# #             clean_concepts, clean_relationships = self._stitch_global_graph(raw_concepts, raw_relationships)
# #             master_knowledge["concepts"] = clean_concepts
# #             master_knowledge["relationships"] = clean_relationships

# #             # 5. Save Final Artifact
# #             extracted_knowledge_path = processed_base / "extracted_knowledge.json"
# #             with open(extracted_knowledge_path, "w", encoding="utf-8") as kf:
# #                 json.dump(master_knowledge, kf, indent=4)

# #             # 6. Update Pipeline Metadata
# #             if metadata_path.exists():
# #                 with open(metadata_path, "r+", encoding="utf-8") as mf:
# #                     meta_data = json.load(mf)
# #                     meta_data["pipeline_status"] = "KNOWLEDGE_EXTRACTED"
# #                     meta_data["next_step"] = f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
# #                     mf.seek(0)
# #                     json.dump(meta_data, mf, indent=2)
# #                     mf.truncate()

# #             logger.info(f"Extraction complete for {document_id}. "
# #                         f"Concepts: {len(clean_concepts)} (Stitched), "
# #                         f"Relationships: {len(clean_relationships)}")

# #             return {
# #                 "document_id": document_id,
# #                 "pipeline_status": "KNOWLEDGE_EXTRACTED",
# #                 "extracted_stats": {
# #                     "raw_concepts_found": len(raw_concepts),
# #                     "clean_concepts_saved": len(clean_concepts),
# #                     "relationships_extracted": len(clean_relationships)
# #                 },
# #                 "knowledge_artifact_path": str(extracted_knowledge_path.relative_to(settings.BASE_DIR))
# #             }

# #         except Exception as e:
# #             logger.error(f"Knowledge extraction failed for {document_id}: {str(e)}", exc_info=True)
# #             raise StorageError(f"Knowledge extraction failed: {str(e)}")








# import json
# import asyncio
# import re
# from pathlib import Path
# from typing import Dict, Any, List, Tuple
# from openai import AsyncOpenAI

# # Graceful token counting (TikToken preferred, character heuristic fallback)
# try:
#     import tiktoken
#     _TOKENIZER = tiktoken.get_encoding("cl100k_base")
#     def count_tokens(text: str) -> int:
#         if not text: return 0
#         return len(_TOKENIZER.encode(text))
# except ImportError:
#     def count_tokens(text: str) -> int:
#         if not text: return 0
#         return len(text) // 4

# from app.core.config import settings
# from app.core.exceptions import DocumentNotFoundError, ProcessingError, StorageError
# from app.core.logger import logger
# from app.models.knowledge import KnowledgeExtractionPayload


# class KnowledgeService:
#     def __init__(self):
#         self.raw_dir = settings.STORAGE_RAW_DIR
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR
        
#         self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
#         self.model_name = "gpt-4o-mini" # or "gpt-4o" for complex sensory reasoning
        
#         self.max_concurrent_requests = getattr(settings, "MAX_CONCURRENT_EXTRACTIONS", 5)
#         self.max_tokens_per_chunk = 6000  # Conservative limit to leave room for LLM JSON output
#         self.overlap_elements = 3         # Applied ONLY during fallback chunking

#         # Controlled Vocabulary for Enterprise Graph Consistency
#         self.ontology_categories = [
#             "Entity", "Method", "Theory", "Process", "Material", 
#             "Chemical", "Instrument", "Organization", "Measurement", "Property", "Sensory_Attribute"
#         ]

#     ###########################################################################
#     # STAGE 1: HIERARCHY-DRIVEN DOCUMENT SPLITTING
#     ###########################################################################

#     def _render_table_markdown(self, cells: List[Dict]) -> str:
#         """Reconstructs the 2D grid from flat cell provenance for LLM ingestion."""
#         if not cells: return ""
#         max_r = max((c.get("row_idx", 0) for c in cells), default=-1)
#         max_c = max((c.get("col_idx", 0) for c in cells), default=-1)
#         if max_r < 0 or max_c < 0: return ""
        
#         grid = [["" for _ in range(max_c + 1)] for _ in range(max_r + 1)]
#         for c in cells:
#             r, col = c.get("row_idx", 0), c.get("col_idx", 0)
#             if r <= max_r and col <= max_c:
#                 grid[r][col] = str(c.get("text", "")).replace("\n", " ").strip()
        
#         md = []
#         for r_idx, row in enumerate(grid):
#             md.append("| " + " | ".join(row) + " |")
#             if r_idx == 0:
#                 md.append("|" + "|".join(["---"] * len(row)) + "|")
#         return "\n".join(md)

#     def _get_element_text(self, el: Dict) -> str:
#         """Safely extracts text for token counting, factoring in tables."""
#         t = el.get("type", "")
#         if t == "table":
#             return self._render_table_markdown(el.get("cells", []))
#         return str(el.get("text", ""))

#     def _hierarchical_split(self, elements: List[Dict], book_title: str, depth: int) -> List[Dict]:
#         """
#         Recursively attempts to fit the largest possible logical document unit 
#         (Chapter -> Section -> Sub-section) into the LLM context window.
#         """
#         if not elements:
#             return []

#         # Check total token size of current logical block
#         text_content = " ".join([self._get_element_text(e) for e in elements])
#         total_tokens = count_tokens(text_content)

#         # If the entire chapter/section fits, return it as one unified payload
#         if total_tokens <= self.max_tokens_per_chunk:
#             return [{"book_title": book_title, "elements": elements}]

#         # If it exceeds limits, group elements by their sub-hierarchy at current depth
#         groups, group_keys = [], []
#         current_key, current_group = None, []

#         for el in elements:
#             path_nodes = el.get("context", {}).get("path", [])
#             path_texts = [p.get("text", "") for p in path_nodes]
#             key = path_texts[depth] if depth < len(path_texts) else ""
            
#             if key != current_key:
#                 if current_group:
#                     groups.append(current_group)
#                     group_keys.append(current_key)
#                 current_key = key
#                 current_group = []
#             current_group.append(el)
            
#         if current_group:
#             groups.append(current_group)
#             group_keys.append(current_key)

#         # If all elements belong to the exact same lowest-level subsection but STILL 
#         # exceed token limits, we are forced to use overlap chunking.
#         if len(groups) == 1:
#             return self._fallback_linear_split(elements, book_title)

#         # Otherwise, recurse deeper into the hierarchy
#         chunks = []
#         for grp in groups:
#             chunks.extend(self._hierarchical_split(grp, book_title, depth + 1))

#         return chunks

#     def _fallback_linear_split(self, elements: List[Dict], book_title: str) -> List[Dict]:
#         """Last resort: Splits an oversized subsection using a sliding overlap window."""
#         chunks, current_chunk = [], []
#         current_tokens = 0

#         for i, el in enumerate(elements):
#             el_text = self._get_element_text(el)
#             el_tokens = count_tokens(el_text) + 15  # Buffer for formatting overhead
            
#             current_chunk.append(el)
#             current_tokens += el_tokens

#             # Split only at natural boundaries
#             is_boundary = el.get("type") in ["paragraph", "heading", "image_occurrence", "table", "caption"]
            
#             if current_tokens > self.max_tokens_per_chunk and is_boundary and i < len(elements) - 1:
#                 chunks.append({"book_title": book_title, "elements": current_chunk})
                
#                 # Create overlapping context to prevent breaking relationships
#                 overlap = current_chunk[-self.overlap_elements:] if len(current_chunk) > self.overlap_elements else current_chunk
#                 current_chunk = overlap.copy()
#                 current_tokens = sum(count_tokens(self._get_element_text(e)) + 15 for e in current_chunk)

#         if current_chunk:
#             chunks.append({"book_title": book_title, "elements": current_chunk})

#         return chunks

#     def _format_logical_payload(self, chunk: Dict[str, Any]) -> str:
#         """Constructs prompt payload injecting strict Parent Hierarchy above content blocks."""
#         book_title = chunk["book_title"]
#         pages = sorted(list(set([e.get("page_number") for e in chunk["elements"] if e.get("page_number")])))
#         page_str = f"Pages: {pages[0]} - {pages[-1]}" if len(pages) > 1 else f"Page: {pages[0]}" if pages else ""

#         lines = [
#             "=== DOCUMENT CONTEXT ===",
#             f"Book: {book_title}",
#             f"{page_str}",
#             "\n=== CONTENT TO EXTRACT ==="
#         ]

#         current_path = None
#         for el in chunk["elements"]:
#             path_nodes = el.get("context", {}).get("path", [])
#             path = tuple([p.get("text", "") for p in path_nodes])
            
#             # Dynamically inject hierarchy whenever the section changes
#             if path != current_path:
#                 path_str = " > ".join(path) if path else "General Content"
#                 lines.append(f"\n--- HIERARCHY: {path_str} ---")
#                 current_path = path

#             t = el.get("type", "paragraph")
#             if t in ["heading", "paragraph", "caption", "list_item", "equation", "cross_ref", "raw_text"]:
#                 text_content = el.get("text", "").strip()
#                 if text_content:
#                     lines.append(f"[{t.upper()}] {text_content}")
#             elif t == "table":
#                 lines.append(f"[TABLE id={el.get('element_id', 'unknown')}]")
#                 lines.append(self._render_table_markdown(el.get("cells", [])))
#             elif t in ["image_occurrence"]:
#                 lines.append(f"[FIGURE ref={el.get('asset_id', 'unknown')}]")

#         return "\n".join(lines)

#     ###########################################################################
#     # STAGE 2: CONTEXT-AWARE LLM EXTRACTION
#     ###########################################################################

#     async def _process_logical_unit(self, chunk_id: str, chunk: Dict[str, Any]) -> Dict[str, List[Any]]:
#         section_payload = self._format_logical_payload(chunk)
#         first_page = chunk["elements"][0].get("page_number") if chunk["elements"] else None

#         if len(section_payload.strip()) < 100:
#             return {"concepts": [], "relationships": [], "scientific_rules": [], "procedures": []}

#         try:
#             logger.debug(f"Extracting knowledge graph for logical unit {chunk_id}")
            
#             completion = await self.client.beta.chat.completions.parse(
#                 model=self.model_name,
#                 messages=[
#                     {
#                         "role": "system", 
#                         "content": (
#                             "You are an expert scientific Knowledge Graph extraction engine analyzing technical and sensory data.\n"
#                             "STRICT EXTRACTION DIRECTIVES:\n"
#                             "1. EXTRACT ONLY DOMAIN KNOWLEDGE (scientific concepts, methodologies, food items, sensory attributes, scores).\n"
#                             "2. PREVENT FLOATING ATTRIBUTES (ANTI-HALLUCINATION): If you encounter an attribute, score, or ingredient in a TABLE or TEXT (e.g., 'Elaichi - 5.5'), DO NOT extract 'Elaichi' or '5.5' as isolated, meaningless nodes. You MUST establish a relationship binding them to their explicit parent context (e.g., the specific food item, preparation method, or sample) defined in the '--- HIERARCHY: ... ---' markers or Table headers.\n"
#                             "3. ONTOLOGY ENFORCEMENT: The 'category' MUST be one of: " f"{self.ontology_categories}\n"
#                             "4. HIERARCHY AWARENESS: Use the '--- HIERARCHY: ... ---' markers to populate the `hierarchy_context` for every concept.\n"
#                             "5. PREVENT METADATA: Ignore authors, publishers, ISBNs, and copyright notices."
#                         )
#                     },
#                     {
#                         "role": "user", 
#                         "content": f"Extract structured knowledge and relationships from this logical unit:\n\n{section_payload}"
#                     }
#                 ],

#                 # messages=[
#                 #     {
#                 #         "role": "system",
#                 #         "content": (
#                 #             "You are a scientific and sensory knowledge extraction engine. "
#                 #             "Your task is to extract structured domain knowledge from the provided document content.\n\n"

#                 #             "SOURCE-ONLY RULE:\n"
#                 #             "Use ONLY information explicitly present in the provided document content. "
#                 #             "Do not use outside knowledge. "
#                 #             "Do not guess. "
#                 #             "Do not invent concepts, values, relationships, causes, or meanings.\n\n"

#                 #             "1. DOMAIN KNOWLEDGE ONLY:\n"
#                 #             "Extract meaningful scientific and sensory knowledge, including concepts, "
#                 #             "food items, ingredients, sensory attributes, descriptors, measurements, "
#                 #             "scores, scales, methods, procedures, materials, instruments, properties, "
#                 #             "benchmarks, scientific rules, and explicitly stated relationships.\n\n"

#                 #             "2. IGNORE DOCUMENT METADATA:\n"
#                 #             "Do not extract authors, publishers, ISBN numbers, copyright notices, "
#                 #             "edition information, page headers, page footers, or other bibliographic metadata "
#                 #             "as domain concepts.\n\n"

#                 #             "3. HIERARCHY MUST BE PRESERVED:\n"
#                 #             "The input contains markers such as "
#                 #             "'--- HIERARCHY: Chapter > Section > Sub-section ---'. "
#                 #             "Use these markers as document context. "
#                 #             "Every extracted concept must preserve the most relevant hierarchy in "
#                 #             "`hierarchy_context`. "
#                 #             "Do not detach a concept from its section or parent context.\n\n"

#                 #             "4. TABLE CONTEXT IS CRITICAL:\n"
#                 #             "Interpret tables using the table caption, column headers, row headers, "
#                 #             "cell values, surrounding text, and document hierarchy. "
#                 #             "Never interpret a table cell independently when its meaning depends on "
#                 #             "a row, column, header, sample, product, ingredient, attribute, or other parent context.\n\n"

#                 #             "5. PREVENT FLOATING ATTRIBUTES AND VALUES:\n"
#                 #             "Never create isolated nodes from an attribute, ingredient, descriptor, "
#                 #             "score, number, or measurement when its meaning depends on another entity.\n"
#                 #             "For example, if the source contains:\n"
#                 #             "'Food Item | Ingredient | Aroma Intensity'\n"
#                 #             "'Ghee | Elaichi | 5.5'\n"
#                 #             "do NOT create unrelated concepts such as 'Elaichi' and '5.5'. "
#                 #             "Preserve the relationships represented by the table, such as "
#                 #             "Ghee -> contains/uses -> Elaichi and "
#                 #             "Elaichi -> has_aroma_intensity -> 5.5, "
#                 #             "but ONLY when those relationships are supported by the table context.\n\n"

#                 #             "6. NUMERIC VALUES MUST KEEP THEIR MEANING:\n"
#                 #             "Never extract a number as a standalone domain concept. "
#                 #             "A value such as 5.5 must remain associated with the attribute, entity, "
#                 #             "sample, scale, or measurement that gives it meaning.\n"
#                 #             "If the source does not clearly define what a number represents, "
#                 #             "do not invent its meaning.\n\n"

#                 #             "7. RELATIONSHIPS ARE REQUIRED:\n"
#                 #             "Extract explicit relationships between concepts. "
#                 #             "Preserve parent-child, attribute, measurement, method, composition, "
#                 #             "cause-effect, procedural, and related-concept relationships when they "
#                 #             "are explicitly supported by the source.\n\n"

#                 #             "8. DO NOT CREATE RELATIONSHIPS BY PROXIMITY:\n"
#                 #             "Two concepts appearing close to each other does not automatically mean "
#                 #             "they are related. "
#                 #             "Create a relationship only when the source content or its table structure "
#                 #             "supports that relationship.\n\n"

#                 #             "9. PRESERVE MULTI-LEVEL CONTEXT:\n"
#                 #             "Do not flatten a relationship chain.\n"
#                 #             "For example, if the document establishes:\n"
#                 #             "Food -> Ingredient -> Sensory Attribute -> Measurement -> Score\n"
#                 #             "preserve the relevant relationships instead of reducing everything to "
#                 #             "Ingredient -> Score.\n\n"

#                 #             "10. CAUSE AND EFFECT:\n"
#                 #             "Extract cause-effect relationships only when they are explicitly stated "
#                 #             "or clearly represented by the source.\n"
#                 #             "For example, if the source says that adding an ingredient increases aroma, "
#                 #             "extract that relationship. "
#                 #             "Do not infer cause and effect from simple co-occurrence.\n\n"

#                 #             "11. SCIENTIFIC RULES:\n"
#                 #             "Extract scientific rules only when they are explicitly stated or directly "
#                 #             "supported by the provided content. "
#                 #             "Do not add scientific knowledge from your own training knowledge.\n\n"

#                 #             "12. PROCEDURES AND METHODS:\n"
#                 #             "Extract procedures and methods only from the provided document. "
#                 #             "Preserve the important steps, materials, measurements, conditions, "
#                 #             "and relationships when they are present.\n\n"

#                 #             "13. FIGURES AND IMAGES:\n"
#                 #             "If the input contains only a figure or image reference without its actual "
#                 #             "content, do not guess what the figure contains. "
#                 #             "Do not invent concepts from an image that has not been provided to you.\n\n"

#                 #             "14. SYNONYMS:\n"
#                 #             "Extract synonyms only when they are explicitly provided or clearly stated "
#                 #             "in the source. "
#                 #             "Do not generate synonyms from general knowledge.\n\n"

#                 #             "15. CANONICAL NAMES:\n"
#                 #             "Use a clean canonical concept name. "
#                 #             "Do not include scores, measurements, page numbers, or unrelated context "
#                 #             "inside `canonical_name`.\n"
#                 #             "For example, use 'Elaichi' rather than 'Elaichi - 5.5'.\n\n"

#                 #             "16. ONTOLOGY ENFORCEMENT:\n"
#                 #             f"The `category` field MUST be one of: {self.ontology_categories}\n"
#                 #             "Do not create new categories.\n\n"

#                 #             "17. DUPLICATE CONCEPTS:\n"
#                 #             "Do not create multiple concepts for the same concept within the same "
#                 #             "logical context. "
#                 #             "However, do not merge concepts merely because their names look similar "
#                 #             "if their meanings are different.\n\n"

#                 #             "18. HALLUCINATION PREVENTION:\n"
#                 #             "The provided document is the only source of truth. "
#                 #             "If information is missing, leave it unextracted. "
#                 #             "Do not fill missing relationships using common scientific knowledge. "
#                 #             "Do not fabricate measurements. "
#                 #             "Do not fabricate parent entities. "
#                 #             "Do not fabricate table meanings.\n\n"

#                 #             "19. RELATIONSHIP VALIDATION:\n"
#                 #             "Before creating a relationship, verify that the source concept and target "
#                 #             "concept are supported by the document and that the relationship is supported "
#                 #             "by the document context. "
#                 #             "Do not create self-referencing relationships.\n\n"

#                 #             "20. CONTEXT PRIORITY:\n"
#                 #             "When interpreting information, use this order of context:\n"
#                 #             "Document hierarchy -> Section context -> Table caption -> "
#                 #             "Table headers -> Row/column context -> Surrounding text -> Individual value.\n"
#                 #             "Never interpret an isolated value before understanding its surrounding context.\n\n"

#                 #             "21. PROVENANCE:\n"
#                 #             "Preserve the available page and hierarchy context for extracted knowledge. "
#                 #             "Do not create provenance information that is not present in the input.\n\n"

#                 #             "22. OUTPUT:\n"
#                 #             "Return ONLY the structured output defined by the provided Pydantic schema. "
#                 #             "Do not return explanations. "
#                 #             "Do not return markdown. "
#                 #             "Do not return reasoning. "
#                 #             "Do not add fields outside the schema."
#                 #         )
#                 #     },
#                 #     {
#                 #         "role": "user",
#                 #         "content": (
#                 #             "Extract structured scientific and sensory knowledge from the following "
#                 #             "logical document unit.\n\n"
#                 #             "IMPORTANT:\n"
#                 #             "- Preserve document hierarchy.\n"
#                 #             "- Preserve table row and column relationships.\n"
#                 #             "- Do not create floating attributes or measurements.\n"
#                 #             "- Keep numeric values connected to their semantic context.\n"
#                 #             "- Extract relationships only when supported by the source.\n"
#                 #             "- Do not use outside knowledge.\n"
#                 #             "- Do not hallucinate missing information.\n\n"
#                 #             f"DOCUMENT CONTENT:\n\n{section_payload}"
#                 #         )
#                 #     }
#                 # ],
#                 response_format=KnowledgeExtractionPayload,
#                 temperature=0.0
#             )

#             result = completion.choices[0].message.parsed
#             extracted = {"concepts": [], "relationships": [], "scientific_rules": [], "procedures": []}

#             if result:
#                 for c in result.concepts:
#                     c_dict = c.model_dump()
#                     c_dict["hierarchy_context"] = c_dict.get("hierarchy_context") or "Extracted Content"
#                     c_dict["source_page"] = first_page
#                     extracted["concepts"].append(c_dict)

#                 extracted["relationships"] = [r.model_dump() for r in result.relationships]
#                 extracted["scientific_rules"] = [sr.model_dump() for sr in result.scientific_rules]
#                 extracted["procedures"] = [p.model_dump() for p in result.procedures]
                
#             return extracted

#         except Exception as e:
#             logger.error(f"LLM extraction error on logical unit {chunk_id}: {str(e)}")
#             return {"concepts": [], "relationships": [], "scientific_rules": [], "procedures": []}

#     ###########################################################################
#     # STAGE 3: GLOBAL DEDUPLICATION & GRAPH STITCHING
#     ###########################################################################

#     def _normalize_key(self, name: str) -> str:
#         if not name: return "unknown"
#         key = re.sub(r'[^a-z0-9]', '', name.lower())
#         if key.endswith('s') and not key.endswith('ss') and len(key) > 3:
#             key = key[:-1]
#         return key

#     def _stitch_global_graph(
#         self, raw_concepts: List[Dict[str, Any]], raw_relationships: List[Dict[str, Any]]
#     ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
#         """
#         Second-pass Graph Stitching:
#         1. Ontology-aware concept merging via stemmed canonical keys.
#         2. Filters out rogue metadata nodes hallucinated by the LLM.
#         3. Validates relationships: Maps edges strictly to surviving nodes and removes duplicate loops.
#         """
#         merged_concepts = {}
#         metadata_keywords = {"press", "isbn", "copyright", "edition", "publisher", "inc", "ltd", "author"}

#         # Pass 1: Deduplicate Concepts globally across all logical units
#         for c in raw_concepts:
#             c_name = c.get("canonical_name", "").strip()
#             if not c_name: continue
            
#             key = self._normalize_key(c_name)
#             if any(bad in key for bad in metadata_keywords):
#                 continue

#             if key in merged_concepts:
#                 merged_concepts[key]["synonyms"] = list(set(merged_concepts[key].get("synonyms", []) + c.get("synonyms", [])))
#                 merged_kws = list(set(merged_concepts[key].get("keywords", []) + c.get("keywords", [])))
#                 merged_concepts[key]["keywords"] = merged_kws[:5]
                
#                 if c.get("hierarchy_context") and c["hierarchy_context"] not in merged_concepts[key].get("hierarchy_context", ""):
#                     merged_concepts[key]["hierarchy_context"] += f" | {c['hierarchy_context']}"
#             else:
#                 c["canonical_name"] = c_name
#                 c["keywords"] = list(set(c.get("keywords", [])))[:5]
#                 merged_concepts[key] = c

#         # Pass 2: Remap & Validate Relationships
#         valid_keys = set(merged_concepts.keys())
#         clean_relationships = []
#         seen_relationships = set()

#         for r in raw_relationships:
#             src_key = self._normalize_key(r.get("source_concept", "").strip())
#             tgt_key = self._normalize_key(r.get("target_concept", "").strip())

#             if src_key in valid_keys and tgt_key in valid_keys:
#                 if src_key == tgt_key:
#                     continue  

#                 r["source_concept"] = merged_concepts[src_key]["canonical_name"]
#                 r["target_concept"] = merged_concepts[tgt_key]["canonical_name"]

#                 rel_signature = f"{src_key}:::{r.get('relationship_type', 'related')}::{tgt_key}"
#                 if rel_signature not in seen_relationships:
#                     clean_relationships.append(r)
#                     seen_relationships.add(rel_signature)

#         return list(merged_concepts.values()), clean_relationships

#     ###########################################################################
#     # MASTER EXECUTION PIPELINE
#     ###########################################################################

#     async def extract_knowledge(self, document_id: str) -> Dict[str, Any]:
#         processed_base = self.processed_dir / document_id
#         normalized_path = processed_base / "normalized_elements.jsonl"
#         metadata_path = self.raw_dir / document_id / "metadata.json"

#         if not normalized_path.exists():
#             raise DocumentNotFoundError(f"Normalized elements for {document_id} not found. Ensure structural extraction completed successfully.")

#         try:
#             logger.info(f"Starting Hierarchical Semantic Extraction for {document_id}")
            
#             # Fetch book title dynamically if metadata exists
#             book_title = "Scientific Document"
#             if metadata_path.exists():
#                 with open(metadata_path, "r", encoding="utf-8") as mf:
#                     book_title = json.load(mf).get("title", book_title)

#             # Stream normalized JSONL elements 
#             elements = []
#             with open(normalized_path, "r", encoding="utf-8") as f:
#                 for line in f:
#                     if line.strip():
#                         elements.append(json.loads(line))

#             # 1. Build Token-Aware Logical Units (Chapter -> Section -> Sub-section)
#             logical_units = self._hierarchical_split(elements, book_title, depth=0)

#             # 2. Process Logical Units Concurrently
#             sem = asyncio.Semaphore(self.max_concurrent_requests)
            
#             async def bounded_process(u_idx: int, data: Dict[str, Any]):
#                 async with sem:
#                     return await self._process_logical_unit(f"unit_{u_idx}", data)

#             tasks = [bounded_process(i, unit) for i, unit in enumerate(logical_units)]
#             batch_results = await asyncio.gather(*tasks)

#             # 3. Collect Raw Outputs
#             raw_concepts, raw_relationships = [], []
#             master_knowledge = {
#                 "document_id": document_id,
#                 "scientific_rules": [],
#                 "procedures": []
#             }

#             for res in batch_results:
#                 raw_concepts.extend(res.get("concepts", []))
#                 raw_relationships.extend(res.get("relationships", []))
#                 master_knowledge["scientific_rules"].extend(res.get("scientific_rules", []))
#                 master_knowledge["procedures"].extend(res.get("procedures", []))

#             # 4. Global Graph Stitching & Validation
#             clean_concepts, clean_relationships = self._stitch_global_graph(raw_concepts, raw_relationships)
#             master_knowledge["concepts"] = clean_concepts
#             master_knowledge["relationships"] = clean_relationships

#             # 5. Save Final Artifact
#             extracted_knowledge_path = processed_base / "extracted_knowledge.json"
#             with open(extracted_knowledge_path, "w", encoding="utf-8") as kf:
#                 json.dump(master_knowledge, kf, indent=4)

#             # 6. Update Pipeline Metadata
#             if metadata_path.exists():
#                 with open(metadata_path, "r+", encoding="utf-8") as mf:
#                     meta_data = json.load(mf)
#                     meta_data["pipeline_status"] = "KNOWLEDGE_EXTRACTED"
#                     meta_data["next_step"] = f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
#                     mf.seek(0)
#                     json.dump(meta_data, mf, indent=2)
#                     mf.truncate()

#             logger.info(f"Knowledge Extraction complete for {document_id}. "
#                         f"Concepts: {len(clean_concepts)} (Stitched), "
#                         f"Relationships: {len(clean_relationships)}")

#             return {
#                 "document_id": document_id,
#                 "pipeline_status": "KNOWLEDGE_EXTRACTED",
#                 "extracted_stats": {
#                     "raw_concepts_found": len(raw_concepts),
#                     "clean_concepts_saved": len(clean_concepts),
#                     "relationships_extracted": len(clean_relationships)
#                 },
#                 "knowledge_artifact_path": str(extracted_knowledge_path.relative_to(settings.BASE_DIR))
#             }

#         except Exception as e:
#             logger.error(f"Knowledge extraction failed for {document_id}: {str(e)}", exc_info=True)
#             raise StorageError(f"Knowledge extraction failed: {str(e)}")







# import asyncio
# import json
# import re
# import time
# from pathlib import Path
# from typing import Dict, Any, List, Tuple, Optional

# from openai import AsyncOpenAI

# # ---------------------------------------------------------------------------
# # OPTIONAL TOKENIZER
# # ---------------------------------------------------------------------------

# try:
#     import tiktoken

#     _TOKENIZER = tiktoken.get_encoding("cl100k_base")

#     def count_tokens(text: str) -> int:
#         if not text:
#             return 0
#         return len(_TOKENIZER.encode(text))

# except ImportError:

#     def count_tokens(text: str) -> int:
#         if not text:
#             return 0
#         return max(1, len(text) // 4)


# # ---------------------------------------------------------------------------
# # APPLICATION IMPORTS
# # ---------------------------------------------------------------------------

# from app.core.config import settings
# from app.core.exceptions import (
#     DocumentNotFoundError,
#     ProcessingError,
#     StorageError,
# )
# from app.core.logger import logger
# from app.models.knowledge import KnowledgeExtractionPayload


# class KnowledgeService:
#     """
#     Knowledge extraction service.

#     Pipeline:

#         normalized_elements.jsonl
#                     |
#                     v
#         hierarchy-aware chunking
#                     |
#                     v
#         concurrent LLM extraction
#                     |
#                     v
#         global graph stitching
#                     |
#                     v
#         extracted_knowledge.json

#     Main goals:

#         1. Preserve extraction accuracy.
#         2. Reduce unnecessary CPU/tokenization work.
#         3. Increase LLM concurrency safely.
#         4. Prevent structural-extraction race conditions.
#         5. Prevent background-task exceptions from crashing ASGI.
#     """

#     # =========================================================================
#     # CONSTANTS
#     # =========================================================================

#     DEFAULT_MODEL = "gpt-4o-mini"

#     DEFAULT_MAX_CONCURRENT_REQUESTS = 10

#     # Keep this at 6000 for accuracy/context preservation.
#     MAX_TOKENS_PER_CHUNK = 6000

#     OVERLAP_ELEMENTS = 3

#     MIN_PAYLOAD_LENGTH = 100

#     # Structural extraction may still be writing normalized_elements.jsonl
#     # when the knowledge extraction endpoint is triggered.
#     NORMALIZED_FILE_WAIT_SECONDS = 60

#     NORMALIZED_FILE_POLL_INTERVAL = 0.5

#     # Number of retries for transient LLM failures.
#     LLM_MAX_RETRIES = 2

#     # =========================================================================
#     # INITIALIZATION
#     # =========================================================================

#     def __init__(self):

#         self.raw_dir = Path(settings.STORAGE_RAW_DIR)
#         self.processed_dir = Path(settings.STORAGE_PROCESSED_DIR)

#         # ---------------------------------------------------------------------
#         # ONE LONG-LIVED ASYNC OPENAI CLIENT
#         # ---------------------------------------------------------------------

#         self.client = AsyncOpenAI(
#             api_key=settings.OPENAI_API_KEY,
#             timeout=getattr(
#                 settings,
#                 "OPENAI_TIMEOUT",
#                 120.0,
#             ),
#             max_retries=getattr(
#                 settings,
#                 "OPENAI_MAX_RETRIES",
#                 2,
#             ),
#         )

#         # ---------------------------------------------------------------------
#         # MODEL
#         # ---------------------------------------------------------------------

#         self.model_name = getattr(
#             settings,
#             "OPENAI_KNOWLEDGE_MODEL",
#             self.DEFAULT_MODEL,
#         )

#         # ---------------------------------------------------------------------
#         # CONCURRENCY
#         # ---------------------------------------------------------------------

#         self.max_concurrent_requests = max(
#             1,
#             int(
#                 getattr(
#                     settings,
#                     "MAX_CONCURRENT_EXTRACTIONS",
#                     self.DEFAULT_MAX_CONCURRENT_REQUESTS,
#                 )
#             ),
#         )

#         # ---------------------------------------------------------------------
#         # CHUNK CONFIGURATION
#         # ---------------------------------------------------------------------

#         self.max_tokens_per_chunk = self.MAX_TOKENS_PER_CHUNK
#         self.overlap_elements = self.OVERLAP_ELEMENTS

#         # ---------------------------------------------------------------------
#         # CONTROLLED VOCABULARY
#         # ---------------------------------------------------------------------

#         self.ontology_categories = [
#             "Entity",
#             "Method",
#             "Theory",
#             "Process",
#             "Material",
#             "Chemical",
#             "Instrument",
#             "Organization",
#             "Measurement",
#             "Property",
#             "Sensory_Attribute",
#         ]

#         # ---------------------------------------------------------------------
#         # PER-DOCUMENT CACHE
#         #
#         # These are deliberately cleared at the start of each document.
#         # Otherwise a long-running service could keep references from previous
#         # documents and gradually consume memory.
#         # ---------------------------------------------------------------------

#         self._element_text_cache: Dict[int, str] = {}
#         self._element_token_cache: Dict[int, int] = {}

#         # ---------------------------------------------------------------------
#         # STATIC SYSTEM PROMPT
#         # ---------------------------------------------------------------------

#         self._system_prompt = self._build_system_prompt()

#     # =========================================================================
#     # SYSTEM PROMPT
#     # =========================================================================

#     def _build_system_prompt(self) -> str:

#         ontology = ", ".join(
#             self.ontology_categories
#         )

#         return (
#             "You are an expert scientific Knowledge Graph extraction engine "
#             "analyzing technical and sensory data.\n\n"

#             "STRICT EXTRACTION DIRECTIVES:\n"

#             "1. EXTRACT ONLY DOMAIN KNOWLEDGE "
#             "(scientific concepts, methodologies, food items, sensory "
#             "attributes, scores).\n"

#             "2. PREVENT FLOATING ATTRIBUTES: "
#             "If an attribute, score, ingredient, descriptor, or measurement "
#             "appears in TABLE or TEXT, do not create it as an isolated "
#             "meaningless node. Bind it to its explicit parent context "
#             "defined by hierarchy markers, table headers, row context, "
#             "column context, or surrounding text.\n"

#             "3. ONTOLOGY ENFORCEMENT: "
#             f"The category MUST be one of: {ontology}.\n"

#             "4. HIERARCHY AWARENESS: "
#             "Use the --- HIERARCHY: ... --- markers to populate "
#             "hierarchy_context for every concept.\n"

#             "5. PREVENT METADATA: "
#             "Ignore authors, publishers, ISBNs, copyright notices, "
#             "edition information, and bibliographic metadata.\n"

#             "6. SOURCE-ONLY EXTRACTION: "
#             "Use only information explicitly supported by the supplied "
#             "document content.\n"

#             "7. DO NOT INVENT relationships, measurements, meanings, "
#             "scientific rules, procedures, synonyms, or parent entities.\n"

#             "8. NUMERIC VALUES MUST REMAIN ASSOCIATED WITH THEIR "
#             "SEMANTIC CONTEXT.\n"

#             "9. TABLE CONTEXT IS CRITICAL: "
#             "Interpret tables using headers, rows, columns, captions, "
#             "surrounding text, and document hierarchy.\n"

#             "10. RELATIONSHIPS MUST BE SOURCE-SUPPORTED: "
#             "Do not create relationships merely because concepts appear "
#             "near each other.\n"

#             "11. PRESERVE DOCUMENT CONTEXT: "
#             "Keep hierarchy and page information when provided.\n"

#             "12. OUTPUT: "
#             "Return ONLY the structured output defined by the provided "
#             "Pydantic schema."
#         )

#     # =========================================================================
#     # TABLE RENDERING
#     # =========================================================================

#     def _render_table_markdown(
#         self,
#         cells: List[Dict],
#     ) -> str:

#         if not cells:
#             return ""

#         max_r = -1
#         max_c = -1

#         for cell in cells:

#             row_idx = cell.get(
#                 "row_idx",
#                 0,
#             )

#             col_idx = cell.get(
#                 "col_idx",
#                 0,
#             )

#             if row_idx > max_r:
#                 max_r = row_idx

#             if col_idx > max_c:
#                 max_c = col_idx

#         if max_r < 0 or max_c < 0:
#             return ""

#         grid = [
#             ["" for _ in range(max_c + 1)]
#             for _ in range(max_r + 1)
#         ]

#         for cell in cells:

#             row_idx = cell.get(
#                 "row_idx",
#                 0,
#             )

#             col_idx = cell.get(
#                 "col_idx",
#                 0,
#             )

#             if (
#                 0 <= row_idx <= max_r
#                 and 0 <= col_idx <= max_c
#             ):

#                 grid[row_idx][col_idx] = (
#                     str(
#                         cell.get(
#                             "text",
#                             "",
#                         )
#                     )
#                     .replace("\n", " ")
#                     .strip()
#                 )

#         lines = []

#         for row_idx, row in enumerate(grid):

#             lines.append(
#                 "| "
#                 + " | ".join(row)
#                 + " |"
#             )

#             if row_idx == 0:

#                 lines.append(
#                     "|"
#                     + "|".join(
#                         ["---"] * len(row)
#                     )
#                     + "|"
#                 )

#         return "\n".join(lines)

#     # =========================================================================
#     # ELEMENT TEXT
#     # =========================================================================

#     def _get_element_text(
#         self,
#         element: Dict,
#     ) -> str:

#         cache_key = id(element)

#         cached = self._element_text_cache.get(
#             cache_key
#         )

#         if cached is not None:
#             return cached

#         element_type = element.get(
#             "type",
#             "",
#         )

#         if element_type == "table":

#             text = self._render_table_markdown(
#                 element.get(
#                     "cells",
#                     [],
#                 )
#             )

#         else:

#             text = str(
#                 element.get(
#                     "text",
#                     "",
#                 )
#             )

#         self._element_text_cache[
#             cache_key
#         ] = text

#         return text

#     # =========================================================================
#     # ELEMENT TOKEN COUNT
#     # =========================================================================

#     def _get_element_tokens(
#         self,
#         element: Dict,
#     ) -> int:

#         cache_key = id(element)

#         cached = self._element_token_cache.get(
#             cache_key
#         )

#         if cached is not None:
#             return cached

#         text = self._get_element_text(
#             element
#         )

#         tokens = count_tokens(text)

#         self._element_token_cache[
#             cache_key
#         ] = tokens

#         return tokens

#     # =========================================================================
#     # HIERARCHICAL SPLIT
#     # =========================================================================

#     def _hierarchical_split(
#         self,
#         elements: List[Dict],
#         book_title: str,
#         depth: int,
#     ) -> List[Dict]:

#         if not elements:
#             return []

#         # ---------------------------------------------------------------------
#         # Use cached per-element token counts.
#         # Avoid rebuilding a giant string just for token counting.
#         # ---------------------------------------------------------------------

#         total_tokens = sum(
#             self._get_element_tokens(element)
#             for element in elements
#         )

#         if total_tokens <= self.max_tokens_per_chunk:

#             return [
#                 {
#                     "book_title": book_title,
#                     "elements": elements,
#                 }
#             ]

#         # ---------------------------------------------------------------------
#         # GROUP BY CURRENT HIERARCHY LEVEL
#         # ---------------------------------------------------------------------

#         groups: List[List[Dict]] = []

#         current_group: List[Dict] = []

#         current_key: Optional[str] = None

#         for element in elements:

#             path_nodes = (
#                 element
#                 .get("context", {})
#                 .get("path", [])
#             )

#             path_texts = [
#                 node.get(
#                     "text",
#                     "",
#                 )
#                 for node in path_nodes
#             ]

#             key = (
#                 path_texts[depth]
#                 if depth < len(path_texts)
#                 else ""
#             )

#             if key != current_key:

#                 if current_group:
#                     groups.append(
#                         current_group
#                     )

#                 current_key = key
#                 current_group = []

#             current_group.append(element)

#         if current_group:
#             groups.append(
#                 current_group
#             )

#         # ---------------------------------------------------------------------
#         # IF THE LOWEST LOGICAL UNIT IS STILL TOO LARGE
#         # ---------------------------------------------------------------------

#         if len(groups) == 1:

#             return self._fallback_linear_split(
#                 elements,
#                 book_title,
#             )

#         # ---------------------------------------------------------------------
#         # RECURSE
#         # ---------------------------------------------------------------------

#         chunks: List[Dict] = []

#         for group in groups:

#             chunks.extend(
#                 self._hierarchical_split(
#                     group,
#                     book_title,
#                     depth + 1,
#                 )
#             )

#         return chunks

#     # =========================================================================
#     # FALLBACK LINEAR SPLIT
#     # =========================================================================

#     def _fallback_linear_split(
#         self,
#         elements: List[Dict],
#         book_title: str,
#     ) -> List[Dict]:

#         chunks: List[Dict] = []

#         current_chunk: List[Dict] = []

#         current_tokens = 0

#         for index, element in enumerate(elements):

#             element_tokens = (
#                 self._get_element_tokens(
#                     element
#                 )
#                 + 15
#             )

#             current_chunk.append(
#                 element
#             )

#             current_tokens += element_tokens

#             is_boundary = (
#                 element.get("type")
#                 in {
#                     "paragraph",
#                     "heading",
#                     "image_occurrence",
#                     "table",
#                     "caption",
#                 }
#             )

#             if (
#                 current_tokens
#                 > self.max_tokens_per_chunk
#                 and is_boundary
#                 and index < len(elements) - 1
#             ):

#                 chunks.append(
#                     {
#                         "book_title": book_title,
#                         "elements": current_chunk,
#                     }
#                 )

#                 overlap_count = min(
#                     self.overlap_elements,
#                     len(current_chunk),
#                 )

#                 overlap = (
#                     current_chunk[
#                         -overlap_count:
#                     ]
#                     if overlap_count
#                     else []
#                 )

#                 current_chunk = overlap.copy()

#                 current_tokens = sum(
#                     self._get_element_tokens(
#                         element
#                     )
#                     + 15
#                     for element in current_chunk
#                 )

#         if current_chunk:

#             chunks.append(
#                 {
#                     "book_title": book_title,
#                     "elements": current_chunk,
#                 }
#             )

#         return chunks

#     # =========================================================================
#     # FORMAT LOGICAL PAYLOAD
#     # =========================================================================

#     def _format_logical_payload(
#         self,
#         chunk: Dict[str, Any],
#     ) -> str:

#         book_title = chunk[
#             "book_title"
#         ]

#         elements = chunk[
#             "elements"
#         ]

#         pages = sorted(
#             {
#                 element.get(
#                     "page_number"
#                 )
#                 for element in elements
#                 if element.get(
#                     "page_number"
#                 ) is not None
#             }
#         )

#         if len(pages) > 1:

#             page_str = (
#                 f"Pages: {pages[0]} - "
#                 f"{pages[-1]}"
#             )

#         elif pages:

#             page_str = (
#                 f"Page: {pages[0]}"
#             )

#         else:

#             page_str = ""

#         lines = [
#             "=== DOCUMENT CONTEXT ===",
#             f"Book: {book_title}",
#             page_str,
#             "",
#             "=== CONTENT TO EXTRACT ===",
#         ]

#         current_path = None

#         for element in elements:

#             path_nodes = (
#                 element
#                 .get("context", {})
#                 .get("path", [])
#             )

#             path = tuple(
#                 node.get(
#                     "text",
#                     "",
#                 )
#                 for node in path_nodes
#             )

#             if path != current_path:

#                 path_str = (
#                     " > ".join(path)
#                     if path
#                     else "General Content"
#                 )

#                 lines.append(
#                     "\n--- HIERARCHY: "
#                     f"{path_str} ---"
#                 )

#                 current_path = path

#             element_type = element.get(
#                 "type",
#                 "paragraph",
#             )

#             if element_type in {
#                 "heading",
#                 "paragraph",
#                 "caption",
#                 "list_item",
#                 "equation",
#                 "cross_ref",
#                 "raw_text",
#             }:

#                 text_content = (
#                     element.get(
#                         "text",
#                         "",
#                     )
#                     .strip()
#                 )

#                 if text_content:

#                     lines.append(
#                         f"[{element_type.upper()}] "
#                         f"{text_content}"
#                     )

#             elif element_type == "table":

#                 lines.append(
#                     "[TABLE id="
#                     f"{element.get('element_id', 'unknown')}]"
#                 )

#                 lines.append(
#                     self._get_element_text(
#                         element
#                     )
#                 )

#             elif element_type == "image_occurrence":

#                 lines.append(
#                     "[FIGURE ref="
#                     f"{element.get('asset_id', 'unknown')}]"
#                 )

#         return "\n".join(lines)

#     # =========================================================================
#     # EMPTY RESULT
#     # =========================================================================

#     @staticmethod
#     def _empty_extraction() -> Dict[str, List[Any]]:

#         return {
#             "concepts": [],
#             "relationships": [],
#             "scientific_rules": [],
#             "procedures": [],
#         }

#     # =========================================================================
#     # LLM EXTRACTION
#     # =========================================================================

#     async def _process_logical_unit(
#         self,
#         chunk_id: str,
#         chunk: Dict[str, Any],
#     ) -> Dict[str, List[Any]]:

#         start_time = time.perf_counter()

#         section_payload = (
#             self._format_logical_payload(
#                 chunk
#             )
#         )

#         elements = chunk.get(
#             "elements",
#             [],
#         )

#         first_page = (
#             elements[0].get(
#                 "page_number"
#             )
#             if elements
#             else None
#         )

#         if (
#             len(
#                 section_payload.strip()
#             )
#             < self.MIN_PAYLOAD_LENGTH
#         ):

#             return self._empty_extraction()

#         # ---------------------------------------------------------------------
#         # LLM CALL WITH RETRIES
#         # ---------------------------------------------------------------------

#         for attempt in range(
#             self.LLM_MAX_RETRIES + 1
#         ):

#             try:

#                 logger.debug(
#                     f"LLM extraction started: "
#                     f"{chunk_id}, "
#                     f"attempt={attempt + 1}"
#                 )

#                 completion = (
#                     await self.client.beta.chat.completions.parse(
#                         model=self.model_name,

#                         messages=[
#                             {
#                                 "role": "system",
#                                 "content": self._system_prompt,
#                             },
#                             {
#                                 "role": "user",
#                                 "content": (
#                                     "Extract structured "
#                                     "knowledge and relationships "
#                                     "from this logical unit:\n\n"
#                                     f"{section_payload}"
#                                 ),
#                             },
#                         ],

#                         response_format=KnowledgeExtractionPayload,

#                         temperature=0.0,
#                     )
#                 )

#                 message = (
#                     completion
#                     .choices[0]
#                     .message
#                 )

#                 result = message.parsed

#                 if not result:

#                     logger.warning(
#                         f"No structured result returned "
#                         f"for {chunk_id}"
#                     )

#                     return self._empty_extraction()

#                 extracted = (
#                     self._empty_extraction()
#                 )

#                 # -------------------------------------------------------------
#                 # CONCEPTS
#                 # -------------------------------------------------------------

#                 for concept in result.concepts:

#                     concept_dict = (
#                         concept.model_dump()
#                     )

#                     concept_dict[
#                         "hierarchy_context"
#                     ] = (
#                         concept_dict.get(
#                             "hierarchy_context"
#                         )
#                         or "Extracted Content"
#                     )

#                     concept_dict[
#                         "source_page"
#                     ] = first_page

#                     extracted[
#                         "concepts"
#                     ].append(
#                         concept_dict
#                     )

#                 # -------------------------------------------------------------
#                 # RELATIONSHIPS
#                 # -------------------------------------------------------------

#                 extracted[
#                     "relationships"
#                 ] = [
#                     relationship.model_dump()
#                     for relationship
#                     in result.relationships
#                 ]

#                 # -------------------------------------------------------------
#                 # SCIENTIFIC RULES
#                 # -------------------------------------------------------------

#                 extracted[
#                     "scientific_rules"
#                 ] = [
#                     rule.model_dump()
#                     for rule
#                     in result.scientific_rules
#                 ]

#                 # -------------------------------------------------------------
#                 # PROCEDURES
#                 # -------------------------------------------------------------

#                 extracted[
#                     "procedures"
#                 ] = [
#                     procedure.model_dump()
#                     for procedure
#                     in result.procedures
#                 ]

#                 elapsed = (
#                     time.perf_counter()
#                     - start_time
#                 )

#                 logger.debug(
#                     f"LLM extraction completed: "
#                     f"{chunk_id} "
#                     f"in {elapsed:.2f}s"
#                 )

#                 return extracted

#             except Exception as exc:

#                 error_text = str(exc)

#                 logger.warning(
#                     f"LLM extraction failed: "
#                     f"{chunk_id}, "
#                     f"attempt={attempt + 1}/"
#                     f"{self.LLM_MAX_RETRIES + 1}: "
#                     f"{error_text}"
#                 )

#                 # -------------------------------------------------------------
#                 # FINAL ATTEMPT
#                 # -------------------------------------------------------------

#                 if (
#                     attempt
#                     >= self.LLM_MAX_RETRIES
#                 ):

#                     logger.error(
#                         f"LLM extraction permanently "
#                         f"failed for {chunk_id}: "
#                         f"{error_text}",
#                         exc_info=True,
#                     )

#                     return self._empty_extraction()

#                 # -------------------------------------------------------------
#                 # EXPONENTIAL BACKOFF
#                 # -------------------------------------------------------------

#                 await asyncio.sleep(
#                     0.5 * (
#                         2 ** attempt
#                     )
#                 )

#         return self._empty_extraction()

#     # =========================================================================
#     # NORMALIZATION
#     # =========================================================================

#     def _normalize_key(
#         self,
#         name: str,
#     ) -> str:

#         if not name:

#             return "unknown"

#         key = re.sub(
#             r"[^a-z0-9]",
#             "",
#             name.lower(),
#         )

#         if (
#             key.endswith("s")
#             and not key.endswith("ss")
#             and len(key) > 3
#         ):

#             key = key[:-1]

#         return key

#     # =========================================================================
#     # GLOBAL GRAPH STITCHING
#     # =========================================================================

#     def _stitch_global_graph(
#         self,
#         raw_concepts: List[Dict[str, Any]],
#         raw_relationships: List[Dict[str, Any]],
#     ) -> Tuple[
#         List[Dict[str, Any]],
#         List[Dict[str, Any]],
#     ]:

#         merged_concepts: Dict[
#             str,
#             Dict[str, Any],
#         ] = {}

#         metadata_keywords = {
#             "press",
#             "isbn",
#             "copyright",
#             "edition",
#             "publisher",
#             "inc",
#             "ltd",
#             "author",
#         }

#         # ---------------------------------------------------------------------
#         # PASS 1 - CONCEPT DEDUPLICATION
#         # ---------------------------------------------------------------------

#         for concept in raw_concepts:

#             concept_name = (
#                 concept.get(
#                     "canonical_name",
#                     "",
#                 )
#                 .strip()
#             )

#             if not concept_name:
#                 continue

#             key = self._normalize_key(
#                 concept_name
#             )

#             if any(
#                 bad in key
#                 for bad in metadata_keywords
#             ):
#                 continue

#             if key in merged_concepts:

#                 existing = (
#                     merged_concepts[key]
#                 )

#                 # -------------------------------------------------------------
#                 # SYNONYMS
#                 # -------------------------------------------------------------

#                 synonyms = set(
#                     existing.get(
#                         "synonyms",
#                         [],
#                     )
#                 )

#                 synonyms.update(
#                     concept.get(
#                         "synonyms",
#                         [],
#                     )
#                 )

#                 existing[
#                     "synonyms"
#                 ] = list(synonyms)

#                 # -------------------------------------------------------------
#                 # KEYWORDS
#                 # -------------------------------------------------------------

#                 keywords = set(
#                     existing.get(
#                         "keywords",
#                         [],
#                     )
#                 )

#                 keywords.update(
#                     concept.get(
#                         "keywords",
#                         [],
#                     )
#                 )

#                 existing[
#                     "keywords"
#                 ] = list(keywords)[:5]

#                 # -------------------------------------------------------------
#                 # HIERARCHY
#                 # -------------------------------------------------------------

#                 current_hierarchy = (
#                     concept.get(
#                         "hierarchy_context"
#                     )
#                 )

#                 existing_hierarchy = (
#                     existing.get(
#                         "hierarchy_context",
#                         "",
#                     )
#                 )

#                 if (
#                     current_hierarchy
#                     and current_hierarchy
#                     not in existing_hierarchy
#                 ):

#                     existing[
#                         "hierarchy_context"
#                     ] = (
#                         existing_hierarchy
#                         + " | "
#                         + current_hierarchy
#                     )

#             else:

#                 concept[
#                     "canonical_name"
#                 ] = concept_name

#                 concept[
#                     "keywords"
#                 ] = list(
#                     set(
#                         concept.get(
#                             "keywords",
#                             [],
#                         )
#                     )
#                 )[:5]

#                 merged_concepts[
#                     key
#                 ] = concept

#         # ---------------------------------------------------------------------
#         # PASS 2 - RELATIONSHIP VALIDATION
#         # ---------------------------------------------------------------------

#         valid_keys = set(
#             merged_concepts.keys()
#         )

#         clean_relationships = []

#         seen_relationships = set()

#         for relationship in raw_relationships:

#             source_key = (
#                 self._normalize_key(
#                     relationship.get(
#                         "source_concept",
#                         "",
#                     ).strip()
#                 )
#             )

#             target_key = (
#                 self._normalize_key(
#                     relationship.get(
#                         "target_concept",
#                         "",
#                     ).strip()
#                 )
#             )

#             if (
#                 source_key
#                 not in valid_keys
#                 or target_key
#                 not in valid_keys
#             ):
#                 continue

#             if source_key == target_key:
#                 continue

#             relationship[
#                 "source_concept"
#             ] = (
#                 merged_concepts[
#                     source_key
#                 ]["canonical_name"]
#             )

#             relationship[
#                 "target_concept"
#             ] = (
#                 merged_concepts[
#                     target_key
#                 ]["canonical_name"]
#             )

#             relationship_type = (
#                 relationship.get(
#                     "relationship_type",
#                     "related",
#                 )
#             )

#             relationship_signature = (
#                 f"{source_key}:::"
#                 f"{relationship_type}:::"
#                 f"{target_key}"
#             )

#             if (
#                 relationship_signature
#                 in seen_relationships
#             ):
#                 continue

#             clean_relationships.append(
#                 relationship
#             )

#             seen_relationships.add(
#                 relationship_signature
#             )

#         return (
#             list(
#                 merged_concepts.values()
#             ),
#             clean_relationships,
#         )

#     # =========================================================================
#     # WAIT FOR STRUCTURAL EXTRACTION
#     # =========================================================================

#     async def _wait_for_normalized_file(
#         self,
#         normalized_path: Path,
#         document_id: str,
#     ) -> None:
#         """
#         Prevents the common race condition:

#             structural extraction
#                     |
#                     | still creating file
#                     v
#             knowledge extraction starts
#                     |
#                     v
#             normalized_elements.jsonl not found

#         Instead of immediately failing, wait for the file to appear.
#         """

#         if normalized_path.exists():
#             return

#         logger.info(
#             f"Normalized file not ready yet for "
#             f"{document_id}. Waiting up to "
#             f"{self.NORMALIZED_FILE_WAIT_SECONDS}s."
#         )

#         deadline = (
#             time.monotonic()
#             + self.NORMALIZED_FILE_WAIT_SECONDS
#         )

#         while time.monotonic() < deadline:

#             if normalized_path.exists():

#                 logger.info(
#                     f"Normalized elements became "
#                     f"available for {document_id}"
#                 )

#                 return

#             await asyncio.sleep(
#                 self.NORMALIZED_FILE_POLL_INTERVAL
#             )

#         raise ProcessingError(
#             f"Normalized elements are not ready for "
#             f"{document_id}. Expected file: "
#             f"{normalized_path}"
#         )

#     # =========================================================================
#     # LOAD JSONL
#     # =========================================================================

#     def _load_normalized_elements(
#         self,
#         normalized_path: Path,
#     ) -> List[Dict]:

#         elements = []

#         with open(
#             normalized_path,
#             "r",
#             encoding="utf-8",
#         ) as file:

#             for line in file:

#                 line = line.strip()

#                 if not line:
#                     continue

#                 try:

#                     elements.append(
#                         json.loads(line)
#                     )

#                 except json.JSONDecodeError as exc:

#                     logger.warning(
#                         f"Skipping invalid JSONL line "
#                         f"in {normalized_path}: "
#                         f"{exc}"
#                     )

#         return elements

#     # =========================================================================
#     # PRE-CACHE ELEMENTS
#     # =========================================================================

#     def _prepare_element_cache(
#         self,
#         elements: List[Dict],
#     ) -> None:

#         self._element_text_cache.clear()
#         self._element_token_cache.clear()

#         for element in elements:

#             cache_key = id(element)

#             if element.get("type") == "table":

#                 text = (
#                     self._render_table_markdown(
#                         element.get(
#                             "cells",
#                             [],
#                         )
#                     )
#                 )

#             else:

#                 text = str(
#                     element.get(
#                         "text",
#                         "",
#                     )
#                 )

#             self._element_text_cache[
#                 cache_key
#             ] = text

#             self._element_token_cache[
#                 cache_key
#             ] = count_tokens(text)

#     # =========================================================================
#     # MASTER EXECUTION PIPELINE
#     # =========================================================================

#     async def extract_knowledge(
#         self,
#         document_id: str,
#     ) -> Dict[str, Any]:

#         started_at = time.perf_counter()

#         # ---------------------------------------------------------------------
#         # PATHS
#         # ---------------------------------------------------------------------

#         processed_base = (
#             self.processed_dir
#             / document_id
#         )

#         normalized_path = (
#             processed_base
#             / "normalized_elements.jsonl"
#         )

#         metadata_path = (
#             self.raw_dir
#             / document_id
#             / "metadata.json"
#         )

#         try:

#             logger.info(
#                 f"Starting hierarchical semantic "
#                 f"extraction for {document_id}"
#             )

#             # ================================================================
#             # 1. WAIT FOR STRUCTURAL EXTRACTION
#             # ================================================================

#             await self._wait_for_normalized_file(
#                 normalized_path,
#                 document_id,
#             )

#             # ================================================================
#             # 2. BOOK TITLE
#             # ================================================================

#             book_title = (
#                 "Scientific Document"
#             )

#             if metadata_path.exists():

#                 try:

#                     with open(
#                         metadata_path,
#                         "r",
#                         encoding="utf-8",
#                     ) as metadata_file:

#                         metadata = json.load(
#                             metadata_file
#                         )

#                     book_title = metadata.get(
#                         "title",
#                         book_title,
#                     )

#                 except Exception as exc:

#                     logger.warning(
#                         f"Could not read metadata "
#                         f"for {document_id}: "
#                         f"{exc}"
#                     )

#             # ================================================================
#             # 3. LOAD NORMALIZED ELEMENTS
#             # ================================================================

#             elements = (
#                 self._load_normalized_elements(
#                     normalized_path
#                 )
#             )

#             if not elements:

#                 logger.warning(
#                     f"No normalized elements found "
#                     f"for {document_id}"
#                 )

#                 return {
#                     "document_id": document_id,
#                     "pipeline_status": "KNOWLEDGE_EXTRACTED",
#                     "extracted_stats": {
#                         "raw_concepts_found": 0,
#                         "clean_concepts_saved": 0,
#                         "relationships_extracted": 0,
#                     },
#                     "knowledge_artifact_path": str(
#                         (
#                             processed_base
#                             / "extracted_knowledge.json"
#                         ).relative_to(
#                             settings.BASE_DIR
#                         )
#                     ),
#                 }

#             logger.info(
#                 f"Loaded {len(elements)} normalized "
#                 f"elements for {document_id}"
#             )

#             # ================================================================
#             # 4. PRE-CACHE TEXT + TOKENS
#             # ================================================================

#             cache_start = time.perf_counter()

#             self._prepare_element_cache(
#                 elements
#             )

#             cache_elapsed = (
#                 time.perf_counter()
#                 - cache_start
#             )

#             logger.info(
#                 f"Element cache prepared for "
#                 f"{document_id} in "
#                 f"{cache_elapsed:.2f}s"
#             )

#             # ================================================================
#             # 5. BUILD LOGICAL UNITS
#             # ================================================================

#             split_start = time.perf_counter()

#             logical_units = (
#                 self._hierarchical_split(
#                     elements,
#                     book_title,
#                     depth=0,
#                 )
#             )

#             split_elapsed = (
#                 time.perf_counter()
#                 - split_start
#             )

#             total_units = len(
#                 logical_units
#             )

#             logger.info(
#                 f"Created {total_units} logical "
#                 f"units for {document_id} "
#                 f"in {split_elapsed:.2f}s. "
#                 f"Concurrency="
#                 f"{self.max_concurrent_requests}"
#             )

#             # ================================================================
#             # 6. CONCURRENT LLM EXTRACTION
#             # ================================================================

#             semaphore = asyncio.Semaphore(
#                 self.max_concurrent_requests
#             )

#             async def bounded_process(
#                 unit_index: int,
#                 unit_data: Dict[str, Any],
#             ):

#                 async with semaphore:

#                     return await (
#                         self._process_logical_unit(
#                             f"unit_{unit_index}",
#                             unit_data,
#                         )
#                     )

#             tasks = [
#                 asyncio.create_task(
#                     bounded_process(
#                         index,
#                         unit,
#                     )
#                 )
#                 for index, unit
#                 in enumerate(
#                     logical_units
#                 )
#             ]

#             raw_concepts: List[
#                 Dict[str, Any]
#             ] = []

#             raw_relationships: List[
#                 Dict[str, Any]
#             ] = []

#             master_knowledge = {
#                 "document_id": document_id,
#                 "scientific_rules": [],
#                 "procedures": [],
#             }

#             completed = 0

#             llm_start = time.perf_counter()

#             # -----------------------------------------------------------------
#             # as_completed lets us process results as soon as they arrive.
#             # -----------------------------------------------------------------

#             for completed_task in asyncio.as_completed(
#                 tasks
#             ):

#                 try:

#                     result = await (
#                         completed_task
#                     )

#                 except Exception as exc:

#                     logger.error(
#                         f"Unexpected logical-unit "
#                         f"failure for {document_id}: "
#                         f"{exc}",
#                         exc_info=True,
#                     )

#                     result = (
#                         self._empty_extraction()
#                     )

#                 completed += 1

#                 raw_concepts.extend(
#                     result.get(
#                         "concepts",
#                         [],
#                     )
#                 )

#                 raw_relationships.extend(
#                     result.get(
#                         "relationships",
#                         [],
#                     )
#                 )

#                 master_knowledge[
#                     "scientific_rules"
#                 ].extend(
#                     result.get(
#                         "scientific_rules",
#                         [],
#                     )
#                 )

#                 master_knowledge[
#                     "procedures"
#                 ].extend(
#                     result.get(
#                         "procedures",
#                         [],
#                     )
#                 )

#                 logger.debug(
#                     f"Knowledge extraction progress "
#                     f"for {document_id}: "
#                     f"{completed}/{total_units}"
#                 )

#             llm_elapsed = (
#                 time.perf_counter()
#                 - llm_start
#             )

#             logger.info(
#                 f"LLM extraction completed for "
#                 f"{document_id} in "
#                 f"{llm_elapsed:.2f}s"
#             )

#             # ================================================================
#             # 7. GLOBAL GRAPH STITCHING
#             # ================================================================

#             stitch_start = time.perf_counter()

#             (
#                 clean_concepts,
#                 clean_relationships,
#             ) = self._stitch_global_graph(
#                 raw_concepts,
#                 raw_relationships,
#             )

#             stitch_elapsed = (
#                 time.perf_counter()
#                 - stitch_start
#             )

#             master_knowledge[
#                 "concepts"
#             ] = clean_concepts

#             master_knowledge[
#                 "relationships"
#             ] = clean_relationships

#             # ================================================================
#             # 8. SAVE FINAL ARTIFACT
#             # ================================================================

#             extracted_knowledge_path = (
#                 processed_base
#                 / "extracted_knowledge.json"
#             )

#             processed_base.mkdir(
#                 parents=True,
#                 exist_ok=True,
#             )

#             with open(
#                 extracted_knowledge_path,
#                 "w",
#                 encoding="utf-8",
#             ) as knowledge_file:

#                 json.dump(
#                     master_knowledge,
#                     knowledge_file,
#                     indent=4,
#                     ensure_ascii=False,
#                 )

#             # ================================================================
#             # 9. UPDATE PIPELINE METADATA
#             # ================================================================

#             if metadata_path.exists():

#                 try:

#                     with open(
#                         metadata_path,
#                         "r",
#                         encoding="utf-8",
#                     ) as metadata_file:

#                         metadata = json.load(
#                             metadata_file
#                         )

#                     metadata[
#                         "pipeline_status"
#                     ] = "KNOWLEDGE_EXTRACTED"

#                     metadata[
#                         "next_step"
#                     ] = (
#                         f"{settings.API_V1_STR}"
#                         f"/documents/{document_id}"
#                         f"/knowledge"
#                     )

#                     with open(
#                         metadata_path,
#                         "w",
#                         encoding="utf-8",
#                     ) as metadata_file:

#                         json.dump(
#                             metadata,
#                             metadata_file,
#                             indent=2,
#                             ensure_ascii=False,
#                         )

#                 except Exception as exc:

#                     logger.warning(
#                         f"Could not update metadata "
#                         f"for {document_id}: "
#                         f"{exc}"
#                     )

#             # ================================================================
#             # 10. FINAL TIMING
#             # ================================================================

#             total_elapsed = (
#                 time.perf_counter()
#                 - started_at
#             )

#             logger.info(
#                 f"Knowledge extraction complete "
#                 f"for {document_id}. "
#                 f"Concepts: "
#                 f"{len(clean_concepts)} "
#                 f"(stitched), "
#                 f"Relationships: "
#                 f"{len(clean_relationships)}, "
#                 f"Total time: "
#                 f"{total_elapsed:.2f}s, "
#                 f"LLM time: "
#                 f"{llm_elapsed:.2f}s, "
#                 f"Stitch time: "
#                 f"{stitch_elapsed:.2f}s"
#             )

#             # ================================================================
#             # SAME API RESULT STRUCTURE
#             # ================================================================

#             return {
#                 "document_id": document_id,
#                 "pipeline_status": "KNOWLEDGE_EXTRACTED",
#                 "extracted_stats": {
#                     "raw_concepts_found": len(
#                         raw_concepts
#                     ),
#                     "clean_concepts_saved": len(
#                         clean_concepts
#                     ),
#                     "relationships_extracted": len(
#                         clean_relationships
#                     ),
#                 },
#                 "knowledge_artifact_path": str(
#                     extracted_knowledge_path.relative_to(
#                         settings.BASE_DIR
#                     )
#                 ),
#             }

#         # =====================================================================
#         # KNOWN PROCESSING ERROR
#         # =====================================================================

#         except ProcessingError as exc:

#             logger.error(
#                 f"Knowledge extraction could not start "
#                 f"for {document_id}: {exc}"
#             )

#             # Do NOT allow a FastAPI background task to throw an exception
#             # after the 202 response has already been sent.
#             #
#             # Return a controlled result instead.
#             return {
#                 "document_id": document_id,
#                 "pipeline_status": "KNOWLEDGE_EXTRACTION_FAILED",
#                 "error": str(exc),
#                 "extracted_stats": {
#                     "raw_concepts_found": 0,
#                     "clean_concepts_saved": 0,
#                     "relationships_extracted": 0,
#                 },
#             }

#         # =====================================================================
#         # DOCUMENT NOT FOUND
#         # =====================================================================

#         except DocumentNotFoundError as exc:

#             logger.error(
#                 f"Document not ready for knowledge "
#                 f"extraction: {document_id}: {exc}"
#             )

#             return {
#                 "document_id": document_id,
#                 "pipeline_status": "KNOWLEDGE_EXTRACTION_FAILED",
#                 "error": str(exc),
#                 "extracted_stats": {
#                     "raw_concepts_found": 0,
#                     "clean_concepts_saved": 0,
#                     "relationships_extracted": 0,
#                 },
#             }

#         # =====================================================================
#         # UNEXPECTED ERROR
#         # =====================================================================

#         except Exception as exc:

#             logger.error(
#                 f"Knowledge extraction failed "
#                 f"for {document_id}: "
#                 f"{exc}",
#                 exc_info=True,
#             )

#             # IMPORTANT:
#             #
#             # The function is probably executed as a FastAPI background task.
#             # Raising here after a 202 response creates:
#             #
#             # RuntimeError:
#             # Caught handled exception, but response already started.
#             #
#             # Therefore we return a controlled failure result instead.
#             return {
#                 "document_id": document_id,
#                 "pipeline_status": "KNOWLEDGE_EXTRACTION_FAILED",
#                 "error": str(exc),
#                 "extracted_stats": {
#                     "raw_concepts_found": 0,
#                     "clean_concepts_saved": 0,
#                     "relationships_extracted": 0,
#                 },
#             }

#         finally:

#             # -----------------------------------------------------------------
#             # IMPORTANT MEMORY CLEANUP
#             # -----------------------------------------------------------------

#             self._element_text_cache.clear()
#             self._element_token_cache.clear()






# import asyncio
# import json
# import re
# import time
# from pathlib import Path
# from typing import Any, Dict, List, Tuple

# from openai import AsyncOpenAI

# try:
#     import tiktoken

#     _TOKENIZER = tiktoken.get_encoding("cl100k_base")

#     def count_tokens(text: str) -> int:
#         if not text:
#             return 0
#         return len(_TOKENIZER.encode(text))

# except ImportError:

#     def count_tokens(text: str) -> int:
#         if not text:
#             return 0
#         return max(1, len(text) // 4)


# from app.core.config import settings
# from app.core.exceptions import (
#     DocumentNotFoundError,
#     ProcessingError,
#     StorageError,
# )
# from app.core.logger import logger
# from app.models.knowledge import KnowledgeExtractionPayload


# class KnowledgeService:
#     """
#     TagTaste Sensory Knowledge Extraction Service.

#     Pipeline:

#         PDF
#           |
#           v
#         Structural extraction
#           |
#           v
#         normalized_elements.jsonl
#           |
#           v
#         hierarchy-aware sensory chunking
#           |
#           v
#         concurrent structured LLM extraction
#           |
#           v
#         sensory-aware graph validation
#           |
#           v
#         global graph stitching
#           |
#           v
#         extracted_knowledge.json

#     Design goals:

#         1. Preserve existing API response shape.
#         2. Understand complete sensory context.
#         3. Prevent floating sensory attributes and numeric values.
#         4. Preserve table semantics.
#         5. Preserve section/hierarchy context.
#         6. Prevent structural/knowledge extraction race conditions.
#         7. Increase extraction speed using async concurrency.
#         8. Retry transient LLM failures.
#         9. Prevent background-task exceptions from escaping after 202.
#         10. Keep deterministic post-processing.
#     """

#     # ======================================================================
#     # CONSTANTS
#     # ======================================================================

#     DEFAULT_MODEL = "gpt-4o-mini"

#     DEFAULT_MAX_CONCURRENT_REQUESTS = 10

#     # 6000 is intentionally retained to preserve enough sensory context.
#     MAX_TOKENS_PER_CHUNK = 6000

#     # Number of previous structural elements carried into next chunk.
#     OVERLAP_ELEMENTS = 3

#     MIN_PAYLOAD_LENGTH = 100

#     # ----------------------------------------------------------------------
#     # STRUCTURAL EXTRACTION SYNCHRONIZATION
#     # ----------------------------------------------------------------------

#     NORMALIZED_FILE_WAIT_SECONDS = 90.0

#     NORMALIZED_FILE_POLL_INTERVAL = 0.50

#     # Number of successful stable observations required before considering
#     # the normalized file ready.
#     NORMALIZED_FILE_STABLE_CHECKS = 2

#     # ----------------------------------------------------------------------
#     # LLM
#     # ----------------------------------------------------------------------

#     LLM_MAX_RETRIES = 2

#     LLM_RETRY_BASE_DELAY = 0.5

#     # ----------------------------------------------------------------------
#     # METADATA
#     # ----------------------------------------------------------------------

#     METADATA_KEYWORDS = {
#         "press",
#         "isbn",
#         "copyright",
#         "edition",
#         "publisher",
#         "author",
#         "bibliography",
#         "reference",
#     }

#     # ======================================================================
#     # INITIALIZATION
#     # ======================================================================

#     def __init__(self):

#         self.raw_dir = Path(
#             settings.STORAGE_RAW_DIR
#         )

#         self.processed_dir = Path(
#             settings.STORAGE_PROCESSED_DIR
#         )

#         # ------------------------------------------------------------------
#         # LONG-LIVED OPENAI CLIENT
#         # ------------------------------------------------------------------

#         self.client = AsyncOpenAI(
#             api_key=settings.OPENAI_API_KEY,
#             timeout=getattr(
#                 settings,
#                 "OPENAI_TIMEOUT",
#                 120.0,
#             ),
#             max_retries=getattr(
#                 settings,
#                 "OPENAI_MAX_RETRIES",
#                 2,
#             ),
#         )

#         # ------------------------------------------------------------------
#         # MODEL
#         # ------------------------------------------------------------------

#         self.model_name = getattr(
#             settings,
#             "OPENAI_KNOWLEDGE_MODEL",
#             self.DEFAULT_MODEL,
#         )

#         # ------------------------------------------------------------------
#         # CONCURRENCY
#         # ------------------------------------------------------------------

#         configured_concurrency = getattr(
#             settings,
#             "MAX_CONCURRENT_EXTRACTIONS",
#             self.DEFAULT_MAX_CONCURRENT_REQUESTS,
#         )

#         try:
#             configured_concurrency = int(
#                 configured_concurrency
#             )
#         except (
#             TypeError,
#             ValueError,
#         ):
#             configured_concurrency = (
#                 self.DEFAULT_MAX_CONCURRENT_REQUESTS
#             )

#         self.max_concurrent_requests = max(
#             1,
#             configured_concurrency,
#         )

#         # ------------------------------------------------------------------
#         # CHUNKING
#         # ------------------------------------------------------------------

#         self.max_tokens_per_chunk = (
#             self.MAX_TOKENS_PER_CHUNK
#         )

#         self.overlap_elements = (
#             self.OVERLAP_ELEMENTS
#         )

#         # ------------------------------------------------------------------
#         # SENSORY ONTOLOGY
#         # ------------------------------------------------------------------

#         self.ontology_categories = [
#             "Entity",
#             "Method",
#             "Theory",
#             "Process",
#             "Material",
#             "Chemical",
#             "Instrument",
#             "Organization",
#             "Measurement",
#             "Property",
#             "Sensory_Attribute",
#         ]

#         # ------------------------------------------------------------------
#         # SENSORY RELATIONSHIP VOCABULARY
#         # ------------------------------------------------------------------

#         self.sensory_relationships = [
#             "has_sensory_attribute",
#             "has_descriptor",
#             "has_intensity",
#             "has_score",
#             "uses_scale",
#             "measured_by",
#             "evaluated_by",
#             "compared_with",
#             "benchmarked_against",
#             "prepared_by",
#             "contains",
#             "derived_from",
#             "belongs_to",
#             "part_of",
#             "associated_with",
#             "caused_by",
#             "influences",
#             "correlates_with",
#             "defined_by",
#             "measured_under",
#             "tested_by",
#             "has_method",
#             "has_property",
#             "related_to",
#         ]

#         # ------------------------------------------------------------------
#         # PER-DOCUMENT CACHE
#         # ------------------------------------------------------------------

#         self._element_text_cache: Dict[int, str] = {}

#         self._element_token_cache: Dict[int, int] = {}

#         # ------------------------------------------------------------------
#         # STATIC SYSTEM PROMPT
#         # ------------------------------------------------------------------

#         self._system_prompt = (
#             self._build_system_prompt()
#         )

#     # ======================================================================
#     # EMPTY RESULT
#     # ======================================================================

#     @staticmethod
#     def _empty_extraction() -> Dict[str, List[Any]]:
#         return {
#             "concepts": [],
#             "relationships": [],
#             "scientific_rules": [],
#             "procedures": [],
#         }

#     # ======================================================================
#     # SYSTEM PROMPT
#     # ======================================================================

#     def _build_system_prompt(self) -> str:

#         ontology = ", ".join(
#             self.ontology_categories
#         )

#         relationship_types = ", ".join(
#             self.sensory_relationships
#         )

#         return f"""
# You are the primary Knowledge Graph extraction engine for TagTaste.

# TagTaste is a sensory intelligence platform.

# Your job is NOT generic keyword extraction.

# Your job is to understand the COMPLETE SEMANTIC AND SENSORY CONTEXT
# contained in technical documents, sensory evaluation documents,
# product documents, food/beverage documents, sensory studies,
# questionnaires, tasting notes, test reports, scientific documents,
# tables, charts, procedures and methodologies.

# ============================================================
# CORE OBJECTIVE
# ============================================================

# Convert explicit document knowledge into a structured knowledge graph.

# The graph must preserve:

# - product/sample identity
# - sensory attributes
# - sensory descriptors
# - sensory scores
# - sensory intensity
# - measurement scales
# - scale endpoints
# - benchmark/reference products
# - preparation methods
# - evaluation methods
# - panel/test context
# - ingredients/materials
# - chemicals
# - instruments
# - sensory methodology
# - scientific rules
# - procedures
# - relationships between all of the above

# Do NOT flatten sensory information into disconnected keywords.

# ============================================================
# ONTOLOGY
# ============================================================

# Every concept category MUST be one of:

# {ontology}

# ============================================================
# SENSORY UNDERSTANDING
# ============================================================

# Understand sensory concepts such as:

# - appearance
# - aroma
# - odor
# - flavor
# - taste
# - mouthfeel
# - texture
# - tactile properties
# - aftertaste
# - finish
# - overall liking
# - acceptability
# - sweetness
# - sourness
# - bitterness
# - saltiness
# - umami
# - astringency
# - acidity
# - spiciness
# - heat
# - freshness
# - intensity
# - color
# - opacity
# - clarity
# - viscosity
# - creaminess
# - crispness
# - crunchiness
# - hardness
# - softness
# - chewiness
# - juiciness
# - tenderness
# - thickness
# - coating
# - persistence
# - balance

# These are examples, NOT an exhaustive vocabulary.

# If the document explicitly contains another sensory attribute,
# extract it.

# ============================================================
# SENSORY HIERARCHY
# ============================================================

# Preserve semantic hierarchy.

# Example:

# Product
#   -> Sensory Domain
#       -> Sensory Attribute
#           -> Descriptor
#           -> Score
#           -> Intensity
#           -> Scale

# Example:

# "Sample A had sweetness 7 on a 9-point scale."

# The system should understand:

# Sample A
#   -> has_sensory_attribute
# Sweetness
#   -> has_score
# 7
#   -> uses_scale
# 9-point scale

# Do NOT create:

# Sample A
# Sweetness
# 7
# 9-point scale

# as four unrelated concepts.

# ============================================================
# TABLE SEMANTICS
# ============================================================

# Tables are extremely important.

# A table such as:

# Product | Sweetness | Bitterness | Aroma
# Sample A | 7 | 2 | 8

# means:

# Sample A
#   -> Sweetness = 7
#   -> Bitterness = 2
#   -> Aroma = 8

# The values MUST remain attached to their corresponding
# attribute and product/sample.

# Never create floating numeric concepts.

# Likewise:

# Descriptor | Intensity
# Vanilla | Strong

# means:

# Vanilla
#   -> has_intensity
# Strong

# inside the appropriate sensory/product context.

# ============================================================
# NUMERIC CONTEXT
# ============================================================

# Numbers must NEVER be interpreted independently.

# Preserve:

# - score
# - rating
# - intensity
# - concentration
# - percentage
# - temperature
# - pH
# - viscosity
# - time
# - duration
# - measurement
# - scale
# - minimum
# - maximum
# - average
# - median
# - standard deviation
# - benchmark value

# Example:

# "Sweetness = 7/9"

# must preserve:

# Sweetness
#   -> has_score
# 7
#   -> uses_scale
# 9-point scale

# Example:

# "pH 4.2"

# must preserve:

# pH
#   -> has_measurement
# 4.2

# Do NOT invent a relationship if the document does not explicitly
# support it.

# ============================================================
# SENSORY SCORE VS CONCEPT
# ============================================================

# A score such as:

# 5.5

# is not automatically a domain concept.

# It is a measurement/value associated with the concept that the
# document explicitly connects it to.

# Similarly:

# "Strong"

# is not automatically a standalone sensory attribute.

# It may be an intensity or descriptor depending on document context.

# ============================================================
# PRODUCT / SAMPLE CONTEXT
# ============================================================

# Preserve the distinction between:

# - product
# - sample
# - formulation
# - treatment
# - batch
# - benchmark
# - reference
# - control

# If the document explicitly identifies them, preserve them.

# Never merge different samples simply because their names are similar.

# ============================================================
# BENCHMARK CONTEXT
# ============================================================

# If a document says:

# "Sample A was compared with Brand B"

# preserve:

# Sample A
#   -> compared_with
# Brand B

# If the document says:

# "Sample A scored higher than Brand B for sweetness"

# preserve the comparison relationship.

# Do NOT invent a benchmark if none is stated.

# ============================================================
# METHOD CONTEXT
# ============================================================

# Preserve explicit relationships involving:

# - sensory evaluation method
# - test method
# - panel method
# - preparation method
# - cooking method
# - serving condition
# - instrument
# - measurement method
# - analysis method

# Example:

# "Samples were evaluated using a 9-point hedonic scale."

# The scale and evaluation method must remain connected.

# ============================================================
# HIERARCHY
# ============================================================

# The input contains markers such as:

# --- HIERARCHY: Chapter > Sensory Evaluation > Flavor ---

# Use the complete hierarchy context.

# Populate hierarchy_context for extracted concepts.

# Do NOT discard hierarchy.

# ============================================================
# SOURCE-ONLY RULE
# ============================================================

# Use ONLY information explicitly supported by the supplied document.

# Never:

# - invent sensory attributes
# - infer causes
# - infer ingredients
# - infer scientific relationships
# - invent score ranges
# - invent benchmark products
# - invent sensory meanings
# - infer relationships solely because they seem scientifically plausible

# If something is ambiguous, do not invent it.

# ============================================================
# METADATA FILTER
# ============================================================

# Ignore:

# - authors
# - ISBN
# - publisher
# - copyright
# - edition information
# - printing information
# - bibliographic metadata

# unless such information is itself explicitly part of the domain
# knowledge being studied.

# ============================================================
# RELATIONSHIPS
# ============================================================

# Prefer precise relationships.

# Allowed relationship vocabulary includes:

# {relationship_types}

# If no precise relationship is appropriate, use:

# related_to

# Do NOT invent relationship names unnecessarily.

# ============================================================
# DUPLICATE CONTROL
# ============================================================

# Use canonical names.

# Examples:

# "Sweetness"
# "sweetness"
# "Sweet"

# must NOT automatically be merged unless the document supports
# that they refer to the same concept.

# Synonyms may be stored separately from canonical_name.

# ============================================================
# EXTRACTION PRIORITY
# ============================================================

# Priority order:

# 1. Product/sample entities
# 2. Sensory attributes
# 3. Descriptors
# 4. Measurements/scores/intensity
# 5. Scales
# 6. Methods
# 7. Benchmarks/references
# 8. Ingredients/materials
# 9. Scientific concepts
# 10. Procedures
# 11. Explicit relationships

# ============================================================
# IMPORTANT ANTI-HALLUCINATION RULE
# ============================================================

# Every extracted relationship must be supported by the supplied
# document context.

# Every score/value must remain semantically attached to its
# parent concept.

# Every sensory descriptor must remain attached to the appropriate
# product/sample/attribute context.

# Do not produce floating graph nodes.

# ============================================================
# OUTPUT
# ============================================================

# Return ONLY the structured output defined by:

# KnowledgeExtractionPayload

# Do not return explanations.
# Do not return markdown.
# Do not return analysis.
# Do not return commentary.
# """

#     # ======================================================================
#     # TABLE RENDERING
#     # ======================================================================

#     def _render_table_markdown(
#         self,
#         cells: List[Dict],
#     ) -> str:

#         if not cells:
#             return ""

#         max_row = -1
#         max_col = -1

#         for cell in cells:

#             row_idx = cell.get(
#                 "row_idx",
#                 0,
#             )

#             col_idx = cell.get(
#                 "col_idx",
#                 0,
#             )

#             max_row = max(
#                 max_row,
#                 row_idx,
#             )

#             max_col = max(
#                 max_col,
#                 col_idx,
#             )

#         if (
#             max_row < 0
#             or max_col < 0
#         ):
#             return ""

#         grid = [
#             ["" for _ in range(max_col + 1)]
#             for _ in range(max_row + 1)
#         ]

#         for cell in cells:

#             row_idx = cell.get(
#                 "row_idx",
#                 0,
#             )

#             col_idx = cell.get(
#                 "col_idx",
#                 0,
#             )

#             if (
#                 0 <= row_idx <= max_row
#                 and 0 <= col_idx <= max_col
#             ):

#                 value = str(
#                     cell.get(
#                         "text",
#                         "",
#                     )
#                     or ""
#                 )

#                 value = (
#                     value
#                     .replace("\n", " ")
#                     .replace("|", "/")
#                     .strip()
#                 )

#                 grid[row_idx][col_idx] = value

#         lines = []

#         for row_idx, row in enumerate(grid):

#             lines.append(
#                 "| "
#                 + " | ".join(row)
#                 + " |"
#             )

#             if row_idx == 0:

#                 lines.append(
#                     "|"
#                     + "|".join(
#                         ["---"] * len(row)
#                     )
#                     + "|"
#                 )

#         return "\n".join(lines)

#     # ======================================================================
#     # ELEMENT TEXT
#     # ======================================================================

#     def _get_element_text(
#         self,
#         element: Dict,
#     ) -> str:

#         cache_key = id(element)

#         cached = self._element_text_cache.get(
#             cache_key
#         )

#         if cached is not None:
#             return cached

#         if element.get("type") == "table":

#             text = self._render_table_markdown(
#                 element.get(
#                     "cells",
#                     [],
#                 )
#             )

#         else:

#             text = str(
#                 element.get(
#                     "text",
#                     "",
#                 )
#                 or ""
#             )

#         self._element_text_cache[
#             cache_key
#         ] = text

#         return text

#     # ======================================================================
#     # TOKEN COUNT
#     # ======================================================================

#     def _get_element_tokens(
#         self,
#         element: Dict,
#     ) -> int:

#         cache_key = id(element)

#         cached = self._element_token_cache.get(
#             cache_key
#         )

#         if cached is not None:
#             return cached

#         tokens = count_tokens(
#             self._get_element_text(element)
#         )

#         self._element_token_cache[
#             cache_key
#         ] = tokens

#         return tokens

#     # ======================================================================
#     # WAIT FOR NORMALIZED FILE
#     # ======================================================================

#     async def _wait_for_normalized_file(
#         self,
#         normalized_path: Path,
#         document_id: str,
#     ) -> None:
#         """
#         Handles the race condition:

#             structural extraction
#                     |
#                     | still running
#                     v
#             knowledge extraction starts
#                     |
#                     v
#             normalized_elements.jsonl missing

#         Additionally verifies that the file is readable and stable.
#         """

#         deadline = (
#             time.monotonic()
#             + self.NORMALIZED_FILE_WAIT_SECONDS
#         )

#         last_signature = None
#         stable_count = 0

#         while time.monotonic() < deadline:

#             if normalized_path.exists():

#                 try:

#                     stat = normalized_path.stat()

#                     if stat.st_size <= 0:

#                         stable_count = 0

#                     else:

#                         # --------------------------------------------------
#                         # Check that JSONL can actually be read.
#                         # --------------------------------------------------

#                         valid_lines = 0
#                         invalid_lines = 0

#                         with open(
#                             normalized_path,
#                             "r",
#                             encoding="utf-8",
#                         ) as file:

#                             for line_number, line in enumerate(
#                                 file
#                             ):

#                                 line = line.strip()

#                                 if not line:
#                                     continue

#                                 try:
#                                     json.loads(line)
#                                     valid_lines += 1
#                                 except json.JSONDecodeError:
#                                     invalid_lines += 1

#                                     # A file still being written may contain
#                                     # one incomplete final line.
#                                     if (
#                                         line_number > 0
#                                         and invalid_lines <= 1
#                                     ):
#                                         break

#                         signature = (
#                             stat.st_size,
#                             stat.st_mtime_ns,
#                             valid_lines,
#                         )

#                         if (
#                             valid_lines > 0
#                             and invalid_lines == 0
#                         ):

#                             if (
#                                 signature
#                                 == last_signature
#                             ):
#                                 stable_count += 1
#                             else:
#                                 stable_count = 1

#                             last_signature = signature

#                             if (
#                                 stable_count
#                                 >= self.NORMALIZED_FILE_STABLE_CHECKS
#                             ):

#                                 logger.info(
#                                     f"Normalized elements ready "
#                                     f"for {document_id}: "
#                                     f"{valid_lines} records."
#                                 )

#                                 return

#                         else:
#                             stable_count = 0

#                 except (
#                     OSError,
#                     PermissionError,
#                     json.JSONDecodeError,
#                 ) as exc:

#                     logger.debug(
#                         f"Normalized file not readable yet "
#                         f"for {document_id}: {exc}"
#                     )

#             await asyncio.sleep(
#                 self.NORMALIZED_FILE_POLL_INTERVAL
#             )

#         raise ProcessingError(
#             f"Normalized elements are not ready for "
#             f"{document_id} after "
#             f"{self.NORMALIZED_FILE_WAIT_SECONDS:.0f}s. "
#             f"Expected file: {normalized_path}"
#         )

#     # ======================================================================
#     # LOAD NORMALIZED JSONL
#     # ======================================================================

#     def _load_normalized_elements(
#         self,
#         normalized_path: Path,
#     ) -> List[Dict]:

#         elements = []

#         with open(
#             normalized_path,
#             "r",
#             encoding="utf-8",
#         ) as file:

#             for line_number, line in enumerate(
#                 file,
#                 start=1,
#             ):

#                 line = line.strip()

#                 if not line:
#                     continue

#                 try:

#                     value = json.loads(line)

#                     if isinstance(
#                         value,
#                         dict,
#                     ):
#                         elements.append(value)

#                 except json.JSONDecodeError as exc:

#                     logger.warning(
#                         f"Skipping invalid JSONL line "
#                         f"{line_number} in "
#                         f"{normalized_path}: {exc}"
#                     )

#         return elements

#     # ======================================================================
#     # PRE-CACHE
#     # ======================================================================

#     def _prepare_element_cache(
#         self,
#         elements: List[Dict],
#     ) -> None:

#         self._element_text_cache.clear()
#         self._element_token_cache.clear()

#         for element in elements:

#             cache_key = id(element)

#             text = self._get_element_text(
#                 element
#             )

#             self._element_text_cache[
#                 cache_key
#             ] = text

#             self._element_token_cache[
#                 cache_key
#             ] = count_tokens(text)

#     # ======================================================================
#     # HIERARCHY-AWARE CHUNKING
#     # ======================================================================

#     def _hierarchical_split(
#         self,
#         elements: List[Dict],
#         book_title: str,
#         depth: int = 0,
#     ) -> List[Dict]:

#         if not elements:
#             return []

#         total_tokens = sum(
#             self._get_element_tokens(
#                 element
#             )
#             for element in elements
#         )

#         if (
#             total_tokens
#             <= self.max_tokens_per_chunk
#         ):

#             return [
#                 {
#                     "book_title": book_title,
#                     "elements": elements,
#                 }
#             ]

#         groups = []

#         current_group = []

#         current_key = None

#         for element in elements:

#             path_nodes = (
#                 element
#                 .get("context", {})
#                 .get("path", [])
#             )

#             path_texts = [
#                 str(
#                     node.get(
#                         "text",
#                         "",
#                     )
#                 )
#                 for node in path_nodes
#             ]

#             if depth < len(path_texts):
#                 key = path_texts[depth]
#             else:
#                 key = ""

#             if (
#                 current_group
#                 and key != current_key
#             ):

#                 groups.append(
#                     current_group
#                 )

#                 current_group = []

#             current_key = key

#             current_group.append(
#                 element
#             )

#         if current_group:
#             groups.append(
#                 current_group
#             )

#         # --------------------------------------------------------------
#         # If hierarchy cannot split further, use linear token split.
#         # --------------------------------------------------------------

#         if len(groups) == 1:

#             return self._fallback_linear_split(
#                 elements,
#                 book_title,
#             )

#         chunks = []

#         for group in groups:

#             chunks.extend(
#                 self._hierarchical_split(
#                     group,
#                     book_title,
#                     depth + 1,
#                 )
#             )

#         return chunks

#     # ======================================================================
#     # LINEAR FALLBACK SPLIT
#     # ======================================================================

#     def _fallback_linear_split(
#         self,
#         elements: List[Dict],
#         book_title: str,
#     ) -> List[Dict]:

#         chunks = []

#         current_chunk = []

#         current_tokens = 0

#         boundaries = {
#             "paragraph",
#             "heading",
#             "image_occurrence",
#             "table",
#             "caption",
#             "list_item",
#         }

#         for index, element in enumerate(
#             elements
#         ):

#             element_tokens = (
#                 self._get_element_tokens(
#                     element
#                 )
#                 + 15
#             )

#             current_chunk.append(
#                 element
#             )

#             current_tokens += element_tokens

#             is_boundary = (
#                 element.get("type")
#                 in boundaries
#             )

#             should_split = (
#                 current_tokens
#                 >= self.max_tokens_per_chunk
#                 and is_boundary
#                 and index < len(elements) - 1
#             )

#             if should_split:

#                 chunks.append(
#                     {
#                         "book_title": book_title,
#                         "elements": current_chunk,
#                     }
#                 )

#                 overlap_count = min(
#                     self.overlap_elements,
#                     len(current_chunk),
#                 )

#                 overlap = (
#                     current_chunk[
#                         -overlap_count:
#                     ]
#                     if overlap_count
#                     else []
#                 )

#                 current_chunk = (
#                     overlap.copy()
#                 )

#                 current_tokens = sum(
#                     self._get_element_tokens(
#                         item
#                     )
#                     + 15
#                     for item in current_chunk
#                 )

#         if current_chunk:

#             chunks.append(
#                 {
#                     "book_title": book_title,
#                     "elements": current_chunk,
#                 }
#             )

#         return chunks

#     # ======================================================================
#     # FORMAT LOGICAL PAYLOAD
#     # ======================================================================

#     def _format_logical_payload(
#         self,
#         chunk: Dict[str, Any],
#     ) -> str:

#         book_title = chunk.get(
#             "book_title",
#             "Scientific Document",
#         )

#         elements = chunk.get(
#             "elements",
#             [],
#         )

#         pages = sorted(
#             {
#                 e.get("page_number")
#                 for e in elements
#                 if e.get("page_number")
#                 is not None
#             }
#         )

#         if len(pages) > 1:

#             page_context = (
#                 f"Pages: {pages[0]} - {pages[-1]}"
#             )

#         elif pages:

#             page_context = (
#                 f"Page: {pages[0]}"
#             )

#         else:

#             page_context = ""

#         lines = [
#             "=== TAGTASTE DOCUMENT CONTEXT ===",
#             f"Book: {book_title}",
#             page_context,
#             "",
#             "=== IMPORTANT ===",
#             "The following content may contain sensory "
#             "measurements, tables, products, samples, "
#             "descriptors, scales and evaluation methods.",
#             "",
#             "Preserve the complete semantic relationship "
#             "between product/sample, sensory attribute, "
#             "descriptor, score, intensity, scale, benchmark "
#             "and method.",
#             "",
#             "=== CONTENT TO EXTRACT ===",
#         ]

#         current_path = None

#         for element in elements:

#             path_nodes = (
#                 element
#                 .get("context", {})
#                 .get("path", [])
#             )

#             path = tuple(
#                 str(
#                     node.get(
#                         "text",
#                         "",
#                     )
#                 )
#                 for node in path_nodes
#             )

#             if path != current_path:

#                 hierarchy = (
#                     " > ".join(path)
#                     if path
#                     else "General Content"
#                 )

#                 lines.append(
#                     f"\n--- HIERARCHY: {hierarchy} ---"
#                 )

#                 current_path = path

#             element_type = element.get(
#                 "type",
#                 "paragraph",
#             )

#             page_number = element.get(
#                 "page_number"
#             )

#             element_id = element.get(
#                 "element_id",
#                 "unknown",
#             )

#             # --------------------------------------------------------------
#             # Text-like elements
#             # --------------------------------------------------------------

#             if element_type in {
#                 "heading",
#                 "paragraph",
#                 "caption",
#                 "list_item",
#                 "equation",
#                 "cross_ref",
#                 "raw_text",
#             }:

#                 text_content = str(
#                     element.get(
#                         "text",
#                         "",
#                     )
#                     or ""
#                 ).strip()

#                 if text_content:

#                     lines.append(
#                         f"[{element_type.upper()} "
#                         f"page={page_number} "
#                         f"id={element_id}] "
#                         f"{text_content}"
#                     )

#             # --------------------------------------------------------------
#             # Table
#             # --------------------------------------------------------------

#             elif element_type == "table":

#                 lines.append(
#                     f"[TABLE "
#                     f"page={page_number} "
#                     f"id={element_id}]"
#                 )

#                 table_text = (
#                     self._render_table_markdown(
#                         element.get(
#                             "cells",
#                             [],
#                         )
#                     )
#                 )

#                 if table_text:
#                     lines.append(
#                         table_text
#                     )

#             # --------------------------------------------------------------
#             # Image
#             # --------------------------------------------------------------

#             elif element_type == "image_occurrence":

#                 lines.append(
#                     f"[FIGURE "
#                     f"page={page_number} "
#                     f"id={element_id} "
#                     f"ref={element.get('asset_id', 'unknown')}]"
#                 )

#         return "\n".join(lines)

#     # ======================================================================
#     # LLM EXTRACTION
#     # ======================================================================

#     async def _process_logical_unit(
#         self,
#         chunk_id: str,
#         chunk: Dict[str, Any],
#     ) -> Dict[str, List[Any]]:

#         start_time = time.perf_counter()

#         section_payload = (
#             self._format_logical_payload(
#                 chunk
#             )
#         )

#         elements = chunk.get(
#             "elements",
#             [],
#         )

#         first_page = (
#             elements[0].get(
#                 "page_number"
#             )
#             if elements
#             else None
#         )

#         if (
#             len(
#                 section_payload.strip()
#             )
#             < self.MIN_PAYLOAD_LENGTH
#         ):

#             return self._empty_extraction()

#         # ------------------------------------------------------------------
#         # RETRY LOOP
#         # ------------------------------------------------------------------

#         for attempt in range(
#             self.LLM_MAX_RETRIES + 1
#         ):

#             try:

#                 logger.debug(
#                     f"LLM extraction started: "
#                     f"{chunk_id}, "
#                     f"attempt={attempt + 1}"
#                 )

#                 completion = (
#                     await self.client.beta.chat.completions.parse(
#                         model=self.model_name,

#                         messages=[
#                             {
#                                 "role": "system",
#                                 "content": self._system_prompt,
#                             },
#                             {
#                                 "role": "user",
#                                 "content": (
#                                     "Extract the complete sensory "
#                                     "knowledge graph from this "
#                                     "logical document unit.\n\n"
#                                     "IMPORTANT:\n"
#                                     "- Preserve product/sample context.\n"
#                                     "- Preserve sensory attribute context.\n"
#                                     "- Preserve descriptors.\n"
#                                     "- Preserve scores and intensity.\n"
#                                     "- Preserve scale information.\n"
#                                     "- Preserve benchmark/reference context.\n"
#                                     "- Preserve evaluation/preparation methods.\n"
#                                     "- Preserve table row/column semantics.\n"
#                                     "- Do not create floating numbers.\n"
#                                     "- Do not create floating descriptors.\n"
#                                     "- Do not invent relationships.\n\n"
#                                     f"{section_payload}"
#                                 ),
#                             },
#                         ],

#                         response_format=KnowledgeExtractionPayload,

#                         temperature=0.0,
#                     )
#                 )

#                 message = (
#                     completion
#                     .choices[0]
#                     .message
#                 )

#                 result = message.parsed

#                 if not result:

#                     logger.warning(
#                         f"No structured result returned "
#                         f"for {chunk_id}"
#                     )

#                     return self._empty_extraction()

#                 extracted = (
#                     self._empty_extraction()
#                 )

#                 # ----------------------------------------------------------
#                 # CONCEPTS
#                 # ----------------------------------------------------------

#                 for concept in (
#                     result.concepts
#                 ):

#                     concept_dict = (
#                         concept.model_dump()
#                     )

#                     concept_dict[
#                         "hierarchy_context"
#                     ] = (
#                         concept_dict.get(
#                             "hierarchy_context"
#                         )
#                         or "Extracted Content"
#                     )

#                     concept_dict[
#                         "source_page"
#                     ] = first_page

#                     extracted[
#                         "concepts"
#                     ].append(
#                         concept_dict
#                     )

#                 # ----------------------------------------------------------
#                 # RELATIONSHIPS
#                 # ----------------------------------------------------------

#                 extracted[
#                     "relationships"
#                 ] = [
#                     relationship.model_dump()
#                     for relationship
#                     in result.relationships
#                 ]

#                 # ----------------------------------------------------------
#                 # SCIENTIFIC RULES
#                 # ----------------------------------------------------------

#                 extracted[
#                     "scientific_rules"
#                 ] = [
#                     rule.model_dump()
#                     for rule
#                     in result.scientific_rules
#                 ]

#                 # ----------------------------------------------------------
#                 # PROCEDURES
#                 # ----------------------------------------------------------

#                 extracted[
#                     "procedures"
#                 ] = [
#                     procedure.model_dump()
#                     for procedure
#                     in result.procedures
#                 ]

#                 elapsed = (
#                     time.perf_counter()
#                     - start_time
#                 )

#                 logger.debug(
#                     f"LLM extraction completed: "
#                     f"{chunk_id} in "
#                     f"{elapsed:.2f}s"
#                 )

#                 return extracted

#             except Exception as exc:

#                 error_text = str(exc)

#                 logger.warning(
#                     f"LLM extraction failed: "
#                     f"{chunk_id}, "
#                     f"attempt={attempt + 1}/"
#                     f"{self.LLM_MAX_RETRIES + 1}: "
#                     f"{error_text}"
#                 )

#                 if (
#                     attempt
#                     >= self.LLM_MAX_RETRIES
#                 ):

#                     logger.error(
#                         f"LLM extraction permanently "
#                         f"failed for {chunk_id}: "
#                         f"{error_text}",
#                         exc_info=True,
#                     )

#                     return (
#                         self._empty_extraction()
#                     )

#                 delay = (
#                     self.LLM_RETRY_BASE_DELAY
#                     * (2 ** attempt)
#                 )

#                 await asyncio.sleep(
#                     delay
#                 )

#         return self._empty_extraction()

#     # ======================================================================
#     # NORMALIZE KEY
#     # ======================================================================

#     def _normalize_key(
#         self,
#         name: str,
#     ) -> str:

#         if not name:
#             return "unknown"

#         name = str(name).strip().lower()

#         # Normalize common punctuation/spacing.
#         key = re.sub(
#             r"[^a-z0-9]+",
#             "",
#             name,
#         )

#         # Conservative singularization.
#         if (
#             key.endswith("s")
#             and not key.endswith("ss")
#             and len(key) > 3
#         ):
#             key = key[:-1]

#         return key or "unknown"

#     # ======================================================================
#     # METADATA FILTER
#     # ======================================================================

#     def _is_metadata_concept(
#         self,
#         name: str,
#     ) -> bool:

#         key = self._normalize_key(
#             name
#         )

#         if not key:
#             return True

#         return any(
#             keyword in key
#             for keyword
#             in self.METADATA_KEYWORDS
#         )

#     # ======================================================================
#     # GLOBAL GRAPH STITCHING
#     # ======================================================================

#     def _stitch_global_graph(
#         self,
#         raw_concepts: List[Dict[str, Any]],
#         raw_relationships: List[Dict[str, Any]],
#     ) -> Tuple[
#         List[Dict[str, Any]],
#         List[Dict[str, Any]],
#     ]:

#         merged_concepts: Dict[
#             str,
#             Dict[str, Any],
#         ] = {}

#         # ------------------------------------------------------------------
#         # PASS 1
#         # CONCEPT DEDUPLICATION
#         # ------------------------------------------------------------------

#         for raw_concept in raw_concepts:

#             if not isinstance(
#                 raw_concept,
#                 dict,
#             ):
#                 continue

#             concept = dict(
#                 raw_concept
#             )

#             concept_name = str(
#                 concept.get(
#                     "canonical_name",
#                     "",
#                 )
#                 or ""
#             ).strip()

#             if not concept_name:
#                 continue

#             if self._is_metadata_concept(
#                 concept_name
#             ):
#                 continue

#             key = self._normalize_key(
#                 concept_name
#             )

#             if key == "unknown":
#                 continue

#             # --------------------------------------------------------------
#             # Ensure category is valid.
#             # --------------------------------------------------------------

#             category = concept.get(
#                 "category"
#             )

#             if (
#                 category
#                 and category
#                 not in self.ontology_categories
#             ):

#                 concept[
#                     "category"
#                 ] = "Entity"

#             # --------------------------------------------------------------
#             # Normalize lists.
#             # --------------------------------------------------------------

#             synonyms = concept.get(
#                 "synonyms",
#                 [],
#             )

#             if not isinstance(
#                 synonyms,
#                 list,
#             ):
#                 synonyms = [str(synonyms)]

#             keywords = concept.get(
#                 "keywords",
#                 [],
#             )

#             if not isinstance(
#                 keywords,
#                 list,
#             ):
#                 keywords = [str(keywords)]

#             concept[
#                 "synonyms"
#             ] = sorted(
#                 {
#                     str(value).strip()
#                     for value in synonyms
#                     if str(value).strip()
#                 }
#             )

#             concept[
#                 "keywords"
#             ] = sorted(
#                 {
#                     str(value).strip()
#                     for value in keywords
#                     if str(value).strip()
#                 }
#             )[:10]

#             # --------------------------------------------------------------
#             # MERGE
#             # --------------------------------------------------------------

#             if key not in merged_concepts:

#                 concept[
#                     "canonical_name"
#                 ] = concept_name

#                 merged_concepts[
#                     key
#                 ] = concept

#                 continue

#             existing = (
#                 merged_concepts[key]
#             )

#             # --------------------------------------------------------------
#             # SYNONYMS
#             # --------------------------------------------------------------

#             existing_synonyms = set(
#                 existing.get(
#                     "synonyms",
#                     [],
#                 )
#             )

#             existing_synonyms.update(
#                 concept.get(
#                     "synonyms",
#                     [],
#                 )
#             )

#             existing[
#                 "synonyms"
#             ] = sorted(
#                 existing_synonyms
#             )

#             # --------------------------------------------------------------
#             # KEYWORDS
#             # --------------------------------------------------------------

#             existing_keywords = set(
#                 existing.get(
#                     "keywords",
#                     [],
#                 )
#             )

#             existing_keywords.update(
#                 concept.get(
#                     "keywords",
#                     [],
#                 )
#             )

#             existing[
#                 "keywords"
#             ] = sorted(
#                 existing_keywords
#             )[:10]

#             # --------------------------------------------------------------
#             # HIERARCHY
#             # --------------------------------------------------------------

#             current_hierarchy = str(
#                 concept.get(
#                     "hierarchy_context",
#                     "",
#                 )
#                 or ""
#             ).strip()

#             existing_hierarchy = str(
#                 existing.get(
#                     "hierarchy_context",
#                     "",
#                 )
#                 or ""
#             ).strip()

#             if (
#                 current_hierarchy
#                 and current_hierarchy
#                 not in existing_hierarchy
#             ):

#                 if existing_hierarchy:

#                     existing[
#                         "hierarchy_context"
#                     ] = (
#                         existing_hierarchy
#                         + " | "
#                         + current_hierarchy
#                     )

#                 else:

#                     existing[
#                         "hierarchy_context"
#                     ] = current_hierarchy

#         # ------------------------------------------------------------------
#         # PASS 2
#         # RELATIONSHIP VALIDATION
#         # ------------------------------------------------------------------

#         valid_keys = set(
#             merged_concepts.keys()
#         )

#         clean_relationships = []

#         seen_relationships = set()

#         for raw_relationship in (
#             raw_relationships
#         ):

#             if not isinstance(
#                 raw_relationship,
#                 dict,
#             ):
#                 continue

#             relationship = dict(
#                 raw_relationship
#             )

#             source_name = str(
#                 relationship.get(
#                     "source_concept",
#                     "",
#                 )
#                 or ""
#             ).strip()

#             target_name = str(
#                 relationship.get(
#                     "target_concept",
#                     "",
#                 )
#                 or ""
#             ).strip()

#             source_key = (
#                 self._normalize_key(
#                     source_name
#                 )
#             )

#             target_key = (
#                 self._normalize_key(
#                     target_name
#                 )
#             )

#             # --------------------------------------------------------------
#             # Both concepts must exist.
#             # --------------------------------------------------------------

#             if (
#                 source_key
#                 not in valid_keys
#                 or target_key
#                 not in valid_keys
#             ):
#                 continue

#             # --------------------------------------------------------------
#             # Prevent self loops.
#             # --------------------------------------------------------------

#             if source_key == target_key:
#                 continue

#             relationship_type = str(
#                 relationship.get(
#                     "relationship_type",
#                     "related_to",
#                 )
#                 or "related_to"
#             ).strip()

#             if not relationship_type:
#                 relationship_type = (
#                     "related_to"
#                 )

#             # --------------------------------------------------------------
#             # Canonical names
#             # --------------------------------------------------------------

#             relationship[
#                 "source_concept"
#             ] = merged_concepts[
#                 source_key
#             ][
#                 "canonical_name"
#             ]

#             relationship[
#                 "target_concept"
#             ] = merged_concepts[
#                 target_key
#             ][
#                 "canonical_name"
#             ]

#             relationship[
#                 "relationship_type"
#             ] = relationship_type

#             # --------------------------------------------------------------
#             # Deduplicate
#             # --------------------------------------------------------------

#             signature = (
#                 f"{source_key}:::"
#                 f"{relationship_type}:::"
#                 f"{target_key}"
#             )

#             if signature in (
#                 seen_relationships
#             ):
#                 continue

#             seen_relationships.add(
#                 signature
#             )

#             clean_relationships.append(
#                 relationship
#             )

#         return (
#             list(
#                 merged_concepts.values()
#             ),
#             clean_relationships,
#         )

#     # ======================================================================
#     # METADATA READ
#     # ======================================================================

#     def _read_metadata(
#         self,
#         metadata_path: Path,
#     ) -> Dict[str, Any]:

#         if not metadata_path.exists():
#             return {}

#         try:

#             with open(
#                 metadata_path,
#                 "r",
#                 encoding="utf-8",
#             ) as file:

#                 value = json.load(file)

#                 if isinstance(
#                     value,
#                     dict,
#                 ):
#                     return value

#         except Exception as exc:

#             logger.warning(
#                 f"Could not read metadata "
#                 f"{metadata_path}: {exc}"
#             )

#         return {}

#     # ======================================================================
#     # ATOMIC JSON WRITE
#     # ======================================================================

#     def _atomic_write_json(
#         self,
#         path: Path,
#         data: Dict[str, Any],
#     ) -> None:

#         path.parent.mkdir(
#             parents=True,
#             exist_ok=True,
#         )

#         temporary_path = path.with_suffix(
#             path.suffix + ".tmp"
#         )

#         with open(
#             temporary_path,
#             "w",
#             encoding="utf-8",
#         ) as file:

#             json.dump(
#                 data,
#                 file,
#                 indent=4,
#                 ensure_ascii=False,
#             )

#             file.flush()

#         temporary_path.replace(
#             path
#         )

#     # ======================================================================
#     # UPDATE PIPELINE METADATA
#     # ======================================================================

#     def _update_metadata_status(
#         self,
#         metadata_path: Path,
#         document_id: str,
#         status: str,
#     ) -> None:

#         if not metadata_path.exists():
#             return

#         metadata = self._read_metadata(
#             metadata_path
#         )

#         if not metadata:
#             return

#         metadata[
#             "pipeline_status"
#         ] = status

#         if status == "KNOWLEDGE_EXTRACTED":

#             metadata[
#                 "next_step"
#             ] = (
#                 f"{settings.API_V1_STR}"
#                 f"/documents/{document_id}"
#                 f"/knowledge"
#             )

#         elif status == "KNOWLEDGE_EXTRACTION_FAILED":

#             metadata[
#                 "next_step"
#             ] = None

#         try:

#             self._atomic_write_json(
#                 metadata_path,
#                 metadata,
#             )

#         except Exception as exc:

#             logger.warning(
#                 f"Could not update metadata "
#                 f"for {document_id}: {exc}"
#             )

#     # ======================================================================
#     # MASTER PIPELINE
#     # ======================================================================

#     async def extract_knowledge(
#         self,
#         document_id: str,
#     ) -> Dict[str, Any]:

#         started_at = (
#             time.perf_counter()
#         )

#         processed_base = (
#             self.processed_dir
#             / document_id
#         )

#         normalized_path = (
#             processed_base
#             / "normalized_elements.jsonl"
#         )

#         metadata_path = (
#             self.raw_dir
#             / document_id
#             / "metadata.json"
#         )

#         extracted_knowledge_path = (
#             processed_base
#             / "extracted_knowledge.json"
#         )

#         logger.info(
#             f"Starting TagTaste sensory "
#             f"knowledge extraction "
#             f"for {document_id}"
#         )

#         try:

#             # ==============================================================
#             # 1. WAIT FOR STRUCTURAL EXTRACTION
#             # ==============================================================

#             await self._wait_for_normalized_file(
#                 normalized_path,
#                 document_id,
#             )

#             # ==============================================================
#             # 2. DOCUMENT METADATA
#             # ==============================================================

#             metadata = self._read_metadata(
#                 metadata_path
#             )

#             book_title = metadata.get(
#                 "title",
#                 "Scientific Document",
#             )

#             # ==============================================================
#             # 3. LOAD NORMALIZED ELEMENTS
#             # ==============================================================

#             elements = (
#                 self._load_normalized_elements(
#                     normalized_path
#                 )
#             )

#             if not elements:

#                 logger.warning(
#                     f"No normalized elements found "
#                     f"for {document_id}"
#                 )

#                 empty_result = {
#                     "document_id": document_id,
#                     "pipeline_status": (
#                         "KNOWLEDGE_EXTRACTED"
#                     ),
#                     "extracted_stats": {
#                         "raw_concepts_found": 0,
#                         "clean_concepts_saved": 0,
#                         "relationships_extracted": 0,
#                     },
#                     "knowledge_artifact_path": str(
#                         extracted_knowledge_path.relative_to(
#                             settings.BASE_DIR
#                         )
#                     ),
#                 }

#                 self._atomic_write_json(
#                     extracted_knowledge_path,
#                     {
#                         "document_id": document_id,
#                         "concepts": [],
#                         "relationships": [],
#                         "scientific_rules": [],
#                         "procedures": [],
#                     },
#                 )

#                 self._update_metadata_status(
#                     metadata_path,
#                     document_id,
#                     "KNOWLEDGE_EXTRACTED",
#                 )

#                 return empty_result

#             logger.info(
#                 f"Loaded {len(elements)} "
#                 f"normalized elements "
#                 f"for {document_id}"
#             )

#             # ==============================================================
#             # 4. PRE-CACHE
#             # ==============================================================

#             cache_start = (
#                 time.perf_counter()
#             )

#             self._prepare_element_cache(
#                 elements
#             )

#             logger.info(
#                 f"Element cache prepared for "
#                 f"{document_id} in "
#                 f"{time.perf_counter() - cache_start:.2f}s"
#             )

#             # ==============================================================
#             # 5. BUILD LOGICAL UNITS
#             # ==============================================================

#             split_start = (
#                 time.perf_counter()
#             )

#             logical_units = (
#                 self._hierarchical_split(
#                     elements,
#                     book_title,
#                     depth=0,
#                 )
#             )

#             split_elapsed = (
#                 time.perf_counter()
#                 - split_start
#             )

#             total_units = len(
#                 logical_units
#             )

#             logger.info(
#                 f"Created {total_units} "
#                 f"logical sensory units "
#                 f"for {document_id} "
#                 f"in {split_elapsed:.2f}s. "
#                 f"Concurrency="
#                 f"{self.max_concurrent_requests}"
#             )

#             # ==============================================================
#             # 6. CONCURRENT LLM EXTRACTION
#             # ==============================================================

#             semaphore = asyncio.Semaphore(
#                 self.max_concurrent_requests
#             )

#             async def bounded_process(
#                 unit_index: int,
#                 unit_data: Dict[str, Any],
#             ):

#                 async with semaphore:

#                     try:

#                         return await (
#                             self._process_logical_unit(
#                                 f"unit_{unit_index}",
#                                 unit_data,
#                             )
#                         )

#                     except Exception as exc:

#                         logger.error(
#                             f"Unexpected extraction "
#                             f"failure in unit "
#                             f"{unit_index}: "
#                             f"{exc}",
#                             exc_info=True,
#                         )

#                         return (
#                             self._empty_extraction()
#                         )

#             tasks = [
#                 asyncio.create_task(
#                     bounded_process(
#                         index,
#                         unit,
#                     )
#                 )
#                 for index, unit
#                 in enumerate(
#                     logical_units
#                 )
#             ]

#             raw_concepts = []

#             raw_relationships = []

#             scientific_rules = []

#             procedures = []

#             completed = 0

#             llm_start = (
#                 time.perf_counter()
#             )

#             # --------------------------------------------------------------
#             # Consume results as soon as they finish.
#             # --------------------------------------------------------------

#             for completed_task in (
#                 asyncio.as_completed(
#                     tasks
#                 )
#             ):

#                 try:

#                     result = await (
#                         completed_task
#                     )

#                 except Exception as exc:

#                     logger.error(
#                         f"Logical unit failed "
#                         f"for {document_id}: "
#                         f"{exc}",
#                         exc_info=True,
#                     )

#                     result = (
#                         self._empty_extraction()
#                     )

#                 completed += 1

#                 raw_concepts.extend(
#                     result.get(
#                         "concepts",
#                         [],
#                     )
#                 )

#                 raw_relationships.extend(
#                     result.get(
#                         "relationships",
#                         [],
#                     )
#                 )

#                 scientific_rules.extend(
#                     result.get(
#                         "scientific_rules",
#                         [],
#                     )
#                 )

#                 procedures.extend(
#                     result.get(
#                         "procedures",
#                         [],
#                     )
#                 )

#                 logger.debug(
#                     f"Knowledge extraction "
#                     f"progress for "
#                     f"{document_id}: "
#                     f"{completed}/"
#                     f"{total_units}"
#                 )

#             llm_elapsed = (
#                 time.perf_counter()
#                 - llm_start
#             )

#             logger.info(
#                 f"LLM sensory extraction "
#                 f"completed for "
#                 f"{document_id} in "
#                 f"{llm_elapsed:.2f}s"
#             )

#             # ==============================================================
#             # 7. GLOBAL GRAPH STITCHING
#             # ==============================================================

#             stitch_start = (
#                 time.perf_counter()
#             )

#             (
#                 clean_concepts,
#                 clean_relationships,
#             ) = self._stitch_global_graph(
#                 raw_concepts,
#                 raw_relationships,
#             )

#             stitch_elapsed = (
#                 time.perf_counter()
#                 - stitch_start
#             )

#             logger.info(
#                 f"Global sensory graph "
#                 f"stitching completed for "
#                 f"{document_id} in "
#                 f"{stitch_elapsed:.2f}s"
#             )

#             # ==============================================================
#             # 8. BUILD FINAL ARTIFACT
#             # ==============================================================

#             master_knowledge = {
#                 "document_id": document_id,

#                 "concepts": clean_concepts,

#                 "relationships": clean_relationships,

#                 "scientific_rules": (
#                     scientific_rules
#                 ),

#                 "procedures": procedures,
#             }

#             # ==============================================================
#             # 9. ATOMIC SAVE
#             # ==============================================================

#             self._atomic_write_json(
#                 extracted_knowledge_path,
#                 master_knowledge,
#             )

#             # ==============================================================
#             # 10. UPDATE PIPELINE STATUS
#             # ==============================================================

#             self._update_metadata_status(
#                 metadata_path,
#                 document_id,
#                 "KNOWLEDGE_EXTRACTED",
#             )

#             # ==============================================================
#             # 11. FINAL RESPONSE
#             # ==============================================================

#             total_elapsed = (
#                 time.perf_counter()
#                 - started_at
#             )

#             logger.info(
#                 f"TagTaste sensory knowledge "
#                 f"extraction completed for "
#                 f"{document_id} in "
#                 f"{total_elapsed:.2f}s. "
#                 f"Raw concepts="
#                 f"{len(raw_concepts)}, "
#                 f"Clean concepts="
#                 f"{len(clean_concepts)}, "
#                 f"Relationships="
#                 f"{len(clean_relationships)}"
#             )

#             # IMPORTANT:
#             # Keep existing API response shape.

#             return {
#                 "document_id": document_id,
#                 "pipeline_status": (
#                     "KNOWLEDGE_EXTRACTED"
#                 ),
#                 "extracted_stats": {
#                     "raw_concepts_found": len(
#                         raw_concepts
#                     ),
#                     "clean_concepts_saved": len(
#                         clean_concepts
#                     ),
#                     "relationships_extracted": len(
#                         clean_relationships
#                     ),
#                 },
#                 "knowledge_artifact_path": str(
#                     extracted_knowledge_path.relative_to(
#                         settings.BASE_DIR
#                     )
#                 ),
#             }

#         except (
#             DocumentNotFoundError,
#             ProcessingError,
#         ):

#             # --------------------------------------------------------------
#             # DO NOT let these exceptions escape from a background task.
#             # --------------------------------------------------------------

#             logger.error(
#                 f"Knowledge extraction could not "
#                 f"start for {document_id}",
#                 exc_info=True,
#             )

#             self._update_metadata_status(
#                 metadata_path,
#                 document_id,
#                 "KNOWLEDGE_EXTRACTION_FAILED",
#             )

#             # --------------------------------------------------------------
#             # IMPORTANT:
#             #
#             # Returning a controlled result prevents:
#             #
#             # RuntimeError:
#             # Caught handled exception, but response
#             # already started.
#             # --------------------------------------------------------------

#             return {
#                 "document_id": document_id,
#                 "pipeline_status": (
#                     "KNOWLEDGE_EXTRACTION_FAILED"
#                 ),
#                 "extracted_stats": {
#                     "raw_concepts_found": 0,
#                     "clean_concepts_saved": 0,
#                     "relationships_extracted": 0,
#                 },
#                 "knowledge_artifact_path": None,
#             }

#         except Exception as exc:

#             logger.error(
#                 f"Knowledge extraction failed "
#                 f"for {document_id}: "
#                 f"{exc}",
#                 exc_info=True,
#             )

#             self._update_metadata_status(
#                 metadata_path,
#                 document_id,
#                 "KNOWLEDGE_EXTRACTION_FAILED",
#             )

#             # --------------------------------------------------------------
#             # IMPORTANT:
#             # Background task must not raise after 202 response.
#             # --------------------------------------------------------------

#             return {
#                 "document_id": document_id,
#                 "pipeline_status": (
#                     "KNOWLEDGE_EXTRACTION_FAILED"
#                 ),
#                 "extracted_stats": {
#                     "raw_concepts_found": 0,
#                     "clean_concepts_saved": 0,
#                     "relationships_extracted": 0,
#                 },
#                 "knowledge_artifact_path": None,
#             }








# import asyncio
# import json
# import re
# import time
# from pathlib import Path
# from typing import Any, Dict, List, Tuple

# from openai import AsyncOpenAI

# try:
#     import tiktoken

#     _TOKENIZER = tiktoken.get_encoding("cl100k_base")

#     def count_tokens(text: str) -> int:
#         if not text:
#             return 0
#         return len(_TOKENIZER.encode(text))

# except ImportError:

#     def count_tokens(text: str) -> int:
#         if not text:
#             return 0
#         return max(1, len(text) // 4)


# from app.core.config import settings
# from app.core.exceptions import (
#     DocumentNotFoundError,
#     ProcessingError,
#     StorageError,
# )
# from app.core.logger import logger
# from app.models.knowledge import KnowledgeExtractionPayload


# class KnowledgeService:
#     """
#     TagTaste Sensory Knowledge Extraction Service.

#     Pipeline:

#         PDF
#           |
#           v
#         Structural extraction
#           |
#           v
#         normalized_elements.jsonl
#           |
#           v
#         hierarchy-aware sensory chunking
#           |
#           v
#         concurrent structured LLM extraction
#           |
#           v
#         sensory-aware graph validation
#           |
#           v
#         global graph stitching
#           |
#           v
#         extracted_knowledge.json

#     Design goals:

#         1. Preserve existing API response shape.
#         2. Understand complete sensory context.
#         3. Prevent floating sensory attributes and numeric values.
#         4. Preserve table semantics.
#         5. Preserve section/hierarchy context.
#         6. Prevent structural/knowledge extraction race conditions.
#         7. Increase extraction speed using async concurrency.
#         8. Retry transient LLM failures.
#         9. Prevent background-task exceptions from escaping after 202.
#         10. Keep deterministic post-processing.
#     """

#     # ======================================================================
#     # CONSTANTS
#     # ======================================================================

#     DEFAULT_MODEL = "gpt-4o-mini"

#     DEFAULT_MAX_CONCURRENT_REQUESTS = 10

#     # 6000 is intentionally retained to preserve enough sensory context.
#     MAX_TOKENS_PER_CHUNK = 6000

#     # Number of previous structural elements carried into next chunk.
#     OVERLAP_ELEMENTS = 3

#     MIN_PAYLOAD_LENGTH = 100

#     # ----------------------------------------------------------------------
#     # STRUCTURAL EXTRACTION SYNCHRONIZATION
#     # ----------------------------------------------------------------------

#     NORMALIZED_FILE_WAIT_SECONDS = 90.0

#     NORMALIZED_FILE_POLL_INTERVAL = 0.50

#     # Number of successful stable observations required before considering
#     # the normalized file ready.
#     NORMALIZED_FILE_STABLE_CHECKS = 2

#     # ----------------------------------------------------------------------
#     # LLM
#     # ----------------------------------------------------------------------

#     LLM_MAX_RETRIES = 2

#     LLM_RETRY_BASE_DELAY = 0.5

#     # ----------------------------------------------------------------------
#     # METADATA
#     # ----------------------------------------------------------------------

#     METADATA_KEYWORDS = {
#         "press",
#         "isbn",
#         "copyright",
#         "edition",
#         "publisher",
#         "author",
#         "bibliography",
#         "reference",
#     }

#     # ======================================================================
#     # INITIALIZATION
#     # ======================================================================

#     def __init__(self):

#         self.raw_dir = Path(
#             settings.STORAGE_RAW_DIR
#         )

#         self.processed_dir = Path(
#             settings.STORAGE_PROCESSED_DIR
#         )

#         # ------------------------------------------------------------------
#         # LONG-LIVED OPENAI CLIENT
#         # ------------------------------------------------------------------

#         self.client = AsyncOpenAI(
#             api_key=settings.OPENAI_API_KEY,
#             timeout=getattr(
#                 settings,
#                 "OPENAI_TIMEOUT",
#                 120.0,
#             ),
#             max_retries=getattr(
#                 settings,
#                 "OPENAI_MAX_RETRIES",
#                 2,
#             ),
#         )

#         # ------------------------------------------------------------------
#         # MODEL
#         # ------------------------------------------------------------------

#         self.model_name = getattr(
#             settings,
#             "OPENAI_KNOWLEDGE_MODEL",
#             self.DEFAULT_MODEL,
#         )

#         # ------------------------------------------------------------------
#         # CONCURRENCY
#         # ------------------------------------------------------------------

#         configured_concurrency = getattr(
#             settings,
#             "MAX_CONCURRENT_EXTRACTIONS",
#             self.DEFAULT_MAX_CONCURRENT_REQUESTS,
#         )

#         try:
#             configured_concurrency = int(
#                 configured_concurrency
#             )
#         except (
#             TypeError,
#             ValueError,
#         ):
#             configured_concurrency = (
#                 self.DEFAULT_MAX_CONCURRENT_REQUESTS
#             )

#         self.max_concurrent_requests = max(
#             1,
#             configured_concurrency,
#         )

#         # ------------------------------------------------------------------
#         # CHUNKING
#         # ------------------------------------------------------------------

#         self.max_tokens_per_chunk = (
#             self.MAX_TOKENS_PER_CHUNK
#         )

#         self.overlap_elements = (
#             self.OVERLAP_ELEMENTS
#         )

#         # ------------------------------------------------------------------
#         # SENSORY ONTOLOGY
#         # ------------------------------------------------------------------

#         self.ontology_categories = [
#             "Entity",
#             "Method",
#             "Theory",
#             "Process",
#             "Material",
#             "Chemical",
#             "Instrument",
#             "Organization",
#             "Measurement",
#             "Property",
#             "Sensory_Attribute",
#         ]

#         # ------------------------------------------------------------------
#         # SENSORY RELATIONSHIP VOCABULARY
#         # ------------------------------------------------------------------

#         self.sensory_relationships = [
#             "has_sensory_attribute",
#             "has_descriptor",
#             "has_intensity",
#             "has_score",
#             "uses_scale",
#             "measured_by",
#             "evaluated_by",
#             "compared_with",
#             "benchmarked_against",
#             "prepared_by",
#             "contains",
#             "derived_from",
#             "belongs_to",
#             "part_of",
#             "associated_with",
#             "caused_by",
#             "influences",
#             "correlates_with",
#             "defined_by",
#             "measured_under",
#             "tested_by",
#             "has_method",
#             "has_property",
#             "related_to",
#         ]

#         # ------------------------------------------------------------------
#         # PER-DOCUMENT CACHE
#         # ------------------------------------------------------------------

#         self._element_text_cache: Dict[int, str] = {}

#         self._element_token_cache: Dict[int, int] = {}

#         # ------------------------------------------------------------------
#         # STATIC SYSTEM PROMPT
#         # ------------------------------------------------------------------

#         self._system_prompt = (
#             self._build_system_prompt()
#         )

#     # ======================================================================
#     # EMPTY RESULT
#     # ======================================================================

#     @staticmethod
#     def _empty_extraction() -> Dict[str, List[Any]]:
#         return {
#             "concepts": [],
#             "relationships": [],
#             "scientific_rules": [],
#             "procedures": [],
#         }

#     # ======================================================================
#     # SYSTEM PROMPT
#     # ======================================================================

#     def _build_system_prompt(self) -> str:

#         ontology = ", ".join(
#             self.ontology_categories
#         )

#         relationship_types = ", ".join(
#             self.sensory_relationships
#         )

#         return f"""
# You are the primary Knowledge Graph extraction engine for TagTaste.

# TagTaste is a sensory intelligence platform.

# Your job is NOT generic keyword extraction.

# Your job is to understand the COMPLETE SEMANTIC AND SENSORY CONTEXT
# contained in technical documents, sensory evaluation documents,
# product documents, food/beverage documents, sensory studies,
# questionnaires, tasting notes, test reports, scientific documents,
# tables, charts, procedures and methodologies.

# ============================================================
# CORE OBJECTIVE
# ============================================================

# Convert explicit document knowledge into a structured knowledge graph.

# The graph must preserve:

# - product/sample identity
# - sensory attributes
# - sensory descriptors
# - sensory scores
# - sensory intensity
# - measurement scales
# - scale endpoints
# - benchmark/reference products
# - preparation methods
# - evaluation methods
# - panel/test context
# - ingredients/materials
# - chemicals
# - instruments
# - sensory methodology
# - scientific rules
# - procedures
# - relationships between all of the above

# Do NOT flatten sensory information into disconnected keywords.

# ============================================================
# ONTOLOGY
# ============================================================

# Every concept category MUST be one of:

# {ontology}

# ============================================================
# SENSORY UNDERSTANDING
# ============================================================

# Understand sensory concepts such as:

# - appearance
# - aroma
# - odor
# - flavor
# - taste
# - mouthfeel
# - texture
# - tactile properties
# - aftertaste
# - finish
# - overall liking
# - acceptability
# - sweetness
# - sourness
# - bitterness
# - saltiness
# - umami
# - astringency
# - acidity
# - spiciness
# - heat
# - freshness
# - intensity
# - color
# - opacity
# - clarity
# - viscosity
# - creaminess
# - crispness
# - crunchiness
# - hardness
# - softness
# - chewiness
# - juiciness
# - tenderness
# - thickness
# - coating
# - persistence
# - balance

# These are examples, NOT an exhaustive vocabulary.

# If the document explicitly contains another sensory attribute,
# extract it.

# ============================================================
# SENSORY HIERARCHY
# ============================================================

# Preserve semantic hierarchy.

# Example:

# Product
#   -> Sensory Domain
#       -> Sensory Attribute
#           -> Descriptor
#           -> Score
#           -> Intensity
#           -> Scale

# Example:

# "Sample A had sweetness 7 on a 9-point scale."

# The system should understand:

# Sample A
#   -> has_sensory_attribute
# Sweetness
#   -> has_score
# 7
#   -> uses_scale
# 9-point scale

# Do NOT create:

# Sample A
# Sweetness
# 7
# 9-point scale

# as four unrelated concepts.

# ============================================================
# TABLE SEMANTICS
# ============================================================

# Tables are extremely important.

# A table such as:

# Product | Sweetness | Bitterness | Aroma
# Sample A | 7 | 2 | 8

# means:

# Sample A
#   -> Sweetness = 7
#   -> Bitterness = 2
#   -> Aroma = 8

# The values MUST remain attached to their corresponding
# attribute and product/sample.

# Never create floating numeric concepts.

# Likewise:

# Descriptor | Intensity
# Vanilla | Strong

# means:

# Vanilla
#   -> has_intensity
# Strong

# inside the appropriate sensory/product context.

# ============================================================
# NUMERIC CONTEXT
# ============================================================

# Numbers must NEVER be interpreted independently.

# Preserve:

# - score
# - rating
# - intensity
# - concentration
# - percentage
# - temperature
# - pH
# - viscosity
# - time
# - duration
# - measurement
# - scale
# - minimum
# - maximum
# - average
# - median
# - standard deviation
# - benchmark value

# Example:

# "Sweetness = 7/9"

# must preserve:

# Sweetness
#   -> has_score
# 7
#   -> uses_scale
# 9-point scale

# Example:

# "pH 4.2"

# must preserve:

# pH
#   -> has_measurement
# 4.2

# Do NOT invent a relationship if the document does not explicitly
# support it.

# ============================================================
# SENSORY SCORE VS CONCEPT
# ============================================================

# A score such as:

# 5.5

# is not automatically a domain concept.

# It is a measurement/value associated with the concept that the
# document explicitly connects it to.

# Similarly:

# "Strong"

# is not automatically a standalone sensory attribute.

# It may be an intensity or descriptor depending on document context.

# ============================================================
# PRODUCT / SAMPLE CONTEXT
# ============================================================

# Preserve the distinction between:

# - product
# - sample
# - formulation
# - treatment
# - batch
# - benchmark
# - reference
# - control

# If the document explicitly identifies them, preserve them.

# Never merge different samples simply because their names are similar.

# ============================================================
# BENCHMARK CONTEXT
# ============================================================

# If a document says:

# "Sample A was compared with Brand B"

# preserve:

# Sample A
#   -> compared_with
# Brand B

# If the document says:

# "Sample A scored higher than Brand B for sweetness"

# preserve the comparison relationship.

# Do NOT invent a benchmark if none is stated.

# ============================================================
# METHOD CONTEXT
# ============================================================

# Preserve explicit relationships involving:

# - sensory evaluation method
# - test method
# - panel method
# - preparation method
# - cooking method
# - serving condition
# - instrument
# - measurement method
# - analysis method

# Example:

# "Samples were evaluated using a 9-point hedonic scale."

# The scale and evaluation method must remain connected.

# ============================================================
# HIERARCHY
# ============================================================

# The input contains markers such as:

# --- HIERARCHY: Chapter > Sensory Evaluation > Flavor ---

# Use the complete hierarchy context.

# Populate hierarchy_context for extracted concepts.

# Do NOT discard hierarchy.

# ============================================================
# SOURCE-ONLY RULE
# ============================================================

# Use ONLY information explicitly supported by the supplied document.

# Never:

# - invent sensory attributes
# - infer causes
# - infer ingredients
# - infer scientific relationships
# - invent score ranges
# - invent benchmark products
# - invent sensory meanings
# - infer relationships solely because they seem scientifically plausible

# If something is ambiguous, do not invent it.

# ============================================================
# METADATA FILTER
# ============================================================

# Ignore:

# - authors
# - ISBN
# - publisher
# - copyright
# - edition information
# - printing information
# - bibliographic metadata

# unless such information is itself explicitly part of the domain
# knowledge being studied.

# ============================================================
# RELATIONSHIPS
# ============================================================

# Prefer precise relationships.

# Allowed relationship vocabulary includes:

# {relationship_types}

# If no precise relationship is appropriate, use:

# related_to

# Do NOT invent relationship names unnecessarily.

# ============================================================
# DUPLICATE CONTROL
# ============================================================

# Use canonical names.

# Examples:

# "Sweetness"
# "sweetness"
# "Sweet"

# must NOT automatically be merged unless the document supports
# that they refer to the same concept.

# Synonyms may be stored separately from canonical_name.

# ============================================================
# EXTRACTION PRIORITY
# ============================================================

# Priority order:

# 1. Product/sample entities
# 2. Sensory attributes
# 3. Descriptors
# 4. Measurements/scores/intensity
# 5. Scales
# 6. Methods
# 7. Benchmarks/references
# 8. Ingredients/materials
# 9. Scientific concepts
# 10. Procedures
# 11. Explicit relationships

# ============================================================
# IMPORTANT ANTI-HALLUCINATION RULE
# ============================================================

# Every extracted relationship must be supported by the supplied
# document context.

# Every score/value must remain semantically attached to its
# parent concept.

# Every sensory descriptor must remain attached to the appropriate
# product/sample/attribute context.

# Do not produce floating graph nodes.

# ============================================================
# OUTPUT
# ============================================================

# Return ONLY the structured output defined by:

# KnowledgeExtractionPayload

# Do not return explanations.
# Do not return markdown.
# Do not return analysis.
# Do not return commentary.
# """

#     # ======================================================================
#     # TABLE RENDERING
#     # ======================================================================

#     def _render_table_markdown(
#         self,
#         cells: List[Dict],
#     ) -> str:

#         if not cells:
#             return ""

#         max_row = -1
#         max_col = -1

#         for cell in cells:

#             row_idx = cell.get(
#                 "row_idx",
#                 0,
#             )

#             col_idx = cell.get(
#                 "col_idx",
#                 0,
#             )

#             max_row = max(
#                 max_row,
#                 row_idx,
#             )

#             max_col = max(
#                 max_col,
#                 col_idx,
#             )

#         if (
#             max_row < 0
#             or max_col < 0
#         ):
#             return ""

#         grid = [
#             ["" for _ in range(max_col + 1)]
#             for _ in range(max_row + 1)
#         ]

#         for cell in cells:

#             row_idx = cell.get(
#                 "row_idx",
#                 0,
#             )

#             col_idx = cell.get(
#                 "col_idx",
#                 0,
#             )

#             if (
#                 0 <= row_idx <= max_row
#                 and 0 <= col_idx <= max_col
#             ):

#                 value = str(
#                     cell.get(
#                         "text",
#                         "",
#                     )
#                     or ""
#                 )

#                 value = (
#                     value
#                     .replace("\n", " ")
#                     .replace("|", "/")
#                     .strip()
#                 )

#                 grid[row_idx][col_idx] = value

#         lines = []

#         for row_idx, row in enumerate(grid):

#             lines.append(
#                 "| "
#                 + " | ".join(row)
#                 + " |"
#             )

#             if row_idx == 0:

#                 lines.append(
#                     "|"
#                     + "|".join(
#                         ["---"] * len(row)
#                     )
#                     + "|"
#                 )

#         return "\n".join(lines)

#     # ======================================================================
#     # ELEMENT TEXT
#     # ======================================================================

#     def _get_element_text(
#         self,
#         element: Dict,
#     ) -> str:

#         cache_key = id(element)

#         cached = self._element_text_cache.get(
#             cache_key
#         )

#         if cached is not None:
#             return cached

#         if element.get("type") == "table":

#             text = self._render_table_markdown(
#                 element.get(
#                     "cells",
#                     [],
#                 )
#             )

#         else:

#             text = str(
#                 element.get(
#                     "text",
#                     "",
#                 )
#                 or ""
#             )

#         self._element_text_cache[
#             cache_key
#         ] = text

#         return text

#     # ======================================================================
#     # TOKEN COUNT
#     # ======================================================================

#     def _get_element_tokens(
#         self,
#         element: Dict,
#     ) -> int:

#         cache_key = id(element)

#         cached = self._element_token_cache.get(
#             cache_key
#         )

#         if cached is not None:
#             return cached

#         tokens = count_tokens(
#             self._get_element_text(element)
#         )

#         self._element_token_cache[
#             cache_key
#         ] = tokens

#         return tokens

#     # ======================================================================
#     # WAIT FOR NORMALIZED FILE
#     # ======================================================================

#     async def _wait_for_normalized_file(
#         self,
#         normalized_path: Path,
#         document_id: str,
#     ) -> None:
#         """
#         Handles the race condition:

#             structural extraction
#                     |
#                     | still running
#                     v
#             knowledge extraction starts
#                     |
#                     v
#             normalized_elements.jsonl missing

#         Additionally verifies that the file is readable and stable.
#         """

#         deadline = (
#             time.monotonic()
#             + self.NORMALIZED_FILE_WAIT_SECONDS
#         )

#         last_signature = None
#         stable_count = 0

#         while time.monotonic() < deadline:

#             if normalized_path.exists():

#                 try:

#                     stat = normalized_path.stat()

#                     if stat.st_size <= 0:

#                         stable_count = 0

#                     else:

#                         # --------------------------------------------------
#                         # Check that JSONL can actually be read.
#                         # --------------------------------------------------

#                         valid_lines = 0
#                         invalid_lines = 0

#                         with open(
#                             normalized_path,
#                             "r",
#                             encoding="utf-8",
#                         ) as file:

#                             for line_number, line in enumerate(
#                                 file
#                             ):

#                                 line = line.strip()

#                                 if not line:
#                                     continue

#                                 try:
#                                     json.loads(line)
#                                     valid_lines += 1
#                                 except json.JSONDecodeError:
#                                     invalid_lines += 1

#                                     # A file still being written may contain
#                                     # one incomplete final line.
#                                     if (
#                                         line_number > 0
#                                         and invalid_lines <= 1
#                                     ):
#                                         break

#                         signature = (
#                             stat.st_size,
#                             stat.st_mtime_ns,
#                             valid_lines,
#                         )

#                         if (
#                             valid_lines > 0
#                             and invalid_lines == 0
#                         ):

#                             if (
#                                 signature
#                                 == last_signature
#                             ):
#                                 stable_count += 1
#                             else:
#                                 stable_count = 1

#                             last_signature = signature

#                             if (
#                                 stable_count
#                                 >= self.NORMALIZED_FILE_STABLE_CHECKS
#                             ):

#                                 logger.info(
#                                     f"Normalized elements ready "
#                                     f"for {document_id}: "
#                                     f"{valid_lines} records."
#                                 )

#                                 return

#                         else:
#                             stable_count = 0

#                 except (
#                     OSError,
#                     PermissionError,
#                     json.JSONDecodeError,
#                 ) as exc:

#                     logger.debug(
#                         f"Normalized file not readable yet "
#                         f"for {document_id}: {exc}"
#                     )

#             await asyncio.sleep(
#                 self.NORMALIZED_FILE_POLL_INTERVAL
#             )

#         raise ProcessingError(
#             f"Normalized elements are not ready for "
#             f"{document_id} after "
#             f"{self.NORMALIZED_FILE_WAIT_SECONDS:.0f}s. "
#             f"Expected file: {normalized_path}"
#         )

#     # ======================================================================
#     # LOAD NORMALIZED JSONL
#     # ======================================================================

#     def _load_normalized_elements(
#         self,
#         normalized_path: Path,
#     ) -> List[Dict]:

#         elements = []

#         with open(
#             normalized_path,
#             "r",
#             encoding="utf-8",
#         ) as file:

#             for line_number, line in enumerate(
#                 file,
#                 start=1,
#             ):

#                 line = line.strip()

#                 if not line:
#                     continue

#                 try:

#                     value = json.loads(line)

#                     if isinstance(
#                         value,
#                         dict,
#                     ):
#                         elements.append(value)

#                 except json.JSONDecodeError as exc:

#                     logger.warning(
#                         f"Skipping invalid JSONL line "
#                         f"{line_number} in "
#                         f"{normalized_path}: {exc}"
#                     )

#         return elements

#     # ======================================================================
#     # PRE-CACHE
#     # ======================================================================

#     def _prepare_element_cache(
#         self,
#         elements: List[Dict],
#     ) -> None:

#         self._element_text_cache.clear()
#         self._element_token_cache.clear()

#         for element in elements:

#             cache_key = id(element)

#             text = self._get_element_text(
#                 element
#             )

#             self._element_text_cache[
#                 cache_key
#             ] = text

#             self._element_token_cache[
#                 cache_key
#             ] = count_tokens(text)

#     # ======================================================================
#     # HIERARCHY-AWARE CHUNKING
#     # ======================================================================

#     def _hierarchical_split(
#         self,
#         elements: List[Dict],
#         book_title: str,
#         depth: int = 0,
#     ) -> List[Dict]:

#         if not elements:
#             return []

#         total_tokens = sum(
#             self._get_element_tokens(
#                 element
#             )
#             for element in elements
#         )

#         if (
#             total_tokens
#             <= self.max_tokens_per_chunk
#         ):

#             return [
#                 {
#                     "book_title": book_title,
#                     "elements": elements,
#                 }
#             ]

#         groups = []

#         current_group = []

#         current_key = None

#         for element in elements:

#             path_nodes = (
#                 element
#                 .get("context", {})
#                 .get("path", [])
#             )

#             path_texts = [
#                 str(
#                     node.get(
#                         "text",
#                         "",
#                     )
#                 )
#                 for node in path_nodes
#             ]

#             if depth < len(path_texts):
#                 key = path_texts[depth]
#             else:
#                 key = ""

#             if (
#                 current_group
#                 and key != current_key
#             ):

#                 groups.append(
#                     current_group
#                 )

#                 current_group = []

#             current_key = key

#             current_group.append(
#                 element
#             )

#         if current_group:
#             groups.append(
#                 current_group
#             )

#         # --------------------------------------------------------------
#         # If hierarchy cannot split further, use linear token split.
#         # --------------------------------------------------------------

#         if len(groups) == 1:

#             return self._fallback_linear_split(
#                 elements,
#                 book_title,
#             )

#         chunks = []

#         for group in groups:

#             chunks.extend(
#                 self._hierarchical_split(
#                     group,
#                     book_title,
#                     depth + 1,
#                 )
#             )

#         return chunks

#     # ======================================================================
#     # LINEAR FALLBACK SPLIT
#     # ======================================================================

#     def _fallback_linear_split(
#         self,
#         elements: List[Dict],
#         book_title: str,
#     ) -> List[Dict]:

#         chunks = []

#         current_chunk = []

#         current_tokens = 0

#         boundaries = {
#             "paragraph",
#             "heading",
#             "image_occurrence",
#             "table",
#             "caption",
#             "list_item",
#         }

#         for index, element in enumerate(
#             elements
#         ):

#             element_tokens = (
#                 self._get_element_tokens(
#                     element
#                 )
#                 + 15
#             )

#             current_chunk.append(
#                 element
#             )

#             current_tokens += element_tokens

#             is_boundary = (
#                 element.get("type")
#                 in boundaries
#             )

#             should_split = (
#                 current_tokens
#                 >= self.max_tokens_per_chunk
#                 and is_boundary
#                 and index < len(elements) - 1
#             )

#             if should_split:

#                 chunks.append(
#                     {
#                         "book_title": book_title,
#                         "elements": current_chunk,
#                     }
#                 )

#                 overlap_count = min(
#                     self.overlap_elements,
#                     len(current_chunk),
#                 )

#                 overlap = (
#                     current_chunk[
#                         -overlap_count:
#                     ]
#                     if overlap_count
#                     else []
#                 )

#                 current_chunk = (
#                     overlap.copy()
#                 )

#                 current_tokens = sum(
#                     self._get_element_tokens(
#                         item
#                     )
#                     + 15
#                     for item in current_chunk
#                 )

#         if current_chunk:

#             chunks.append(
#                 {
#                     "book_title": book_title,
#                     "elements": current_chunk,
#                 }
#             )

#         return chunks

#     # ======================================================================
#     # FORMAT LOGICAL PAYLOAD
#     # ======================================================================

#     def _format_logical_payload(
#         self,
#         chunk: Dict[str, Any],
#     ) -> str:

#         book_title = chunk.get(
#             "book_title",
#             "Scientific Document",
#         )

#         elements = chunk.get(
#             "elements",
#             [],
#         )

#         pages = sorted(
#             {
#                 e.get("page_number")
#                 for e in elements
#                 if e.get("page_number")
#                 is not None
#             }
#         )

#         if len(pages) > 1:

#             page_context = (
#                 f"Pages: {pages[0]} - {pages[-1]}"
#             )

#         elif pages:

#             page_context = (
#                 f"Page: {pages[0]}"
#             )

#         else:

#             page_context = ""

#         lines = [
#             "=== TAGTASTE DOCUMENT CONTEXT ===",
#             f"Book: {book_title}",
#             page_context,
#             "",
#             "=== IMPORTANT ===",
#             "The following content may contain sensory "
#             "measurements, tables, products, samples, "
#             "descriptors, scales and evaluation methods.",
#             "",
#             "Preserve the complete semantic relationship "
#             "between product/sample, sensory attribute, "
#             "descriptor, score, intensity, scale, benchmark "
#             "and method.",
#             "",
#             "=== CONTENT TO EXTRACT ===",
#         ]

#         current_path = None

#         for element in elements:

#             path_nodes = (
#                 element
#                 .get("context", {})
#                 .get("path", [])
#             )

#             path = tuple(
#                 str(
#                     node.get(
#                         "text",
#                         "",
#                     )
#                 )
#                 for node in path_nodes
#             )

#             if path != current_path:

#                 hierarchy = (
#                     " > ".join(path)
#                     if path
#                     else "General Content"
#                 )

#                 lines.append(
#                     f"\n--- HIERARCHY: {hierarchy} ---"
#                 )

#                 current_path = path

#             element_type = element.get(
#                 "type",
#                 "paragraph",
#             )

#             page_number = element.get(
#                 "page_number"
#             )

#             element_id = element.get(
#                 "element_id",
#                 "unknown",
#             )

#             # --------------------------------------------------------------
#             # Text-like elements
#             # --------------------------------------------------------------

#             if element_type in {
#                 "heading",
#                 "paragraph",
#                 "caption",
#                 "list_item",
#                 "equation",
#                 "cross_ref",
#                 "raw_text",
#             }:

#                 text_content = str(
#                     element.get(
#                         "text",
#                         "",
#                     )
#                     or ""
#                 ).strip()

#                 if text_content:

#                     lines.append(
#                         f"[{element_type.upper()} "
#                         f"page={page_number} "
#                         f"id={element_id}] "
#                         f"{text_content}"
#                     )

#             # --------------------------------------------------------------
#             # Table
#             # --------------------------------------------------------------

#             elif element_type == "table":

#                 lines.append(
#                     f"[TABLE "
#                     f"page={page_number} "
#                     f"id={element_id}]"
#                 )

#                 table_text = (
#                     self._render_table_markdown(
#                         element.get(
#                             "cells",
#                             [],
#                         )
#                     )
#                 )

#                 if table_text:
#                     lines.append(
#                         table_text
#                     )

#             # --------------------------------------------------------------
#             # Image
#             # --------------------------------------------------------------

#             elif element_type == "image_occurrence":

#                 lines.append(
#                     f"[FIGURE "
#                     f"page={page_number} "
#                     f"id={element_id} "
#                     f"ref={element.get('asset_id', 'unknown')}]"
#                 )

#         return "\n".join(lines)

#     # ======================================================================
#     # LLM EXTRACTION
#     # ======================================================================

#     async def _process_logical_unit(
#         self,
#         chunk_id: str,
#         chunk: Dict[str, Any],
#     ) -> Dict[str, List[Any]]:

#         start_time = time.perf_counter()

#         section_payload = (
#             self._format_logical_payload(
#                 chunk
#             )
#         )

#         elements = chunk.get(
#             "elements",
#             [],
#         )

#         first_page = (
#             elements[0].get(
#                 "page_number"
#             )
#             if elements
#             else None
#         )

#         if (
#             len(
#                 section_payload.strip()
#             )
#             < self.MIN_PAYLOAD_LENGTH
#         ):

#             return self._empty_extraction()

#         # ------------------------------------------------------------------
#         # RETRY LOOP
#         # ------------------------------------------------------------------

#         for attempt in range(
#             self.LLM_MAX_RETRIES + 1
#         ):

#             try:

#                 logger.debug(
#                     f"LLM extraction started: "
#                     f"{chunk_id}, "
#                     f"attempt={attempt + 1}"
#                 )

#                 completion = (
#                     await self.client.beta.chat.completions.parse(
#                         model=self.model_name,

#                         messages=[
#                             {
#                                 "role": "system",
#                                 "content": self._system_prompt,
#                             },
#                             {
#                                 "role": "user",
#                                 "content": (
#                                     "Extract the complete sensory "
#                                     "knowledge graph from this "
#                                     "logical document unit.\n\n"
#                                     "IMPORTANT:\n"
#                                     "- Preserve product/sample context.\n"
#                                     "- Preserve sensory attribute context.\n"
#                                     "- Preserve descriptors.\n"
#                                     "- Preserve scores and intensity.\n"
#                                     "- Preserve scale information.\n"
#                                     "- Preserve benchmark/reference context.\n"
#                                     "- Preserve evaluation/preparation methods.\n"
#                                     "- Preserve table row/column semantics.\n"
#                                     "- Do not create floating numbers.\n"
#                                     "- Do not create floating descriptors.\n"
#                                     "- Do not invent relationships.\n\n"
#                                     f"{section_payload}"
#                                 ),
#                             },
#                         ],

#                         response_format=KnowledgeExtractionPayload,

#                         temperature=0.0,
#                     )
#                 )

#                 message = (
#                     completion
#                     .choices[0]
#                     .message
#                 )

#                 result = message.parsed

#                 if not result:

#                     logger.warning(
#                         f"No structured result returned "
#                         f"for {chunk_id}"
#                     )

#                     return self._empty_extraction()

#                 extracted = (
#                     self._empty_extraction()
#                 )

#                 # ----------------------------------------------------------
#                 # CONCEPTS
#                 # ----------------------------------------------------------

#                 for concept in (
#                     result.concepts
#                 ):

#                     concept_dict = (
#                         concept.model_dump()
#                     )

#                     concept_dict[
#                         "hierarchy_context"
#                     ] = (
#                         concept_dict.get(
#                             "hierarchy_context"
#                         )
#                         or "Extracted Content"
#                     )

#                     concept_dict[
#                         "source_page"
#                     ] = first_page

#                     extracted[
#                         "concepts"
#                     ].append(
#                         concept_dict
#                     )

#                 # ----------------------------------------------------------
#                 # RELATIONSHIPS
#                 # ----------------------------------------------------------

#                 extracted[
#                     "relationships"
#                 ] = [
#                     relationship.model_dump()
#                     for relationship
#                     in result.relationships
#                 ]

#                 # ----------------------------------------------------------
#                 # SCIENTIFIC RULES
#                 # ----------------------------------------------------------

#                 extracted[
#                     "scientific_rules"
#                 ] = [
#                     rule.model_dump()
#                     for rule
#                     in result.scientific_rules
#                 ]

#                 # ----------------------------------------------------------
#                 # PROCEDURES
#                 # ----------------------------------------------------------

#                 extracted[
#                     "procedures"
#                 ] = [
#                     procedure.model_dump()
#                     for procedure
#                     in result.procedures
#                 ]

#                 elapsed = (
#                     time.perf_counter()
#                     - start_time
#                 )

#                 logger.debug(
#                     f"LLM extraction completed: "
#                     f"{chunk_id} in "
#                     f"{elapsed:.2f}s"
#                 )

#                 return extracted

#             except Exception as exc:

#                 error_text = str(exc)

#                 logger.warning(
#                     f"LLM extraction failed: "
#                     f"{chunk_id}, "
#                     f"attempt={attempt + 1}/"
#                     f"{self.LLM_MAX_RETRIES + 1}: "
#                     f"{error_text}"
#                 )

#                 if (
#                     attempt
#                     >= self.LLM_MAX_RETRIES
#                 ):

#                     logger.error(
#                         f"LLM extraction permanently "
#                         f"failed for {chunk_id}: "
#                         f"{error_text}",
#                         exc_info=True,
#                     )

#                     return (
#                         self._empty_extraction()
#                     )

#                 delay = (
#                     self.LLM_RETRY_BASE_DELAY
#                     * (2 ** attempt)
#                 )

#                 await asyncio.sleep(
#                     delay
#                 )

#         return self._empty_extraction()

#     # ======================================================================
#     # NORMALIZE KEY
#     # ======================================================================

#     def _normalize_key(
#         self,
#         name: str,
#     ) -> str:

#         if not name:
#             return "unknown"

#         name = str(name).strip().lower()

#         # Normalize common punctuation/spacing.
#         key = re.sub(
#             r"[^a-z0-9]+",
#             "",
#             name,
#         )

#         # Conservative singularization.
#         if (
#             key.endswith("s")
#             and not key.endswith("ss")
#             and len(key) > 3
#         ):
#             key = key[:-1]

#         return key or "unknown"

#     # ======================================================================
#     # METADATA FILTER
#     # ======================================================================

#     def _is_metadata_concept(
#         self,
#         name: str,
#     ) -> bool:

#         key = self._normalize_key(
#             name
#         )

#         if not key:
#             return True

#         return any(
#             keyword in key
#             for keyword
#             in self.METADATA_KEYWORDS
#         )

#     # ======================================================================
#     # GLOBAL GRAPH STITCHING
#     # ======================================================================

#     def _stitch_global_graph(
#         self,
#         raw_concepts: List[Dict[str, Any]],
#         raw_relationships: List[Dict[str, Any]],
#     ) -> Tuple[
#         List[Dict[str, Any]],
#         List[Dict[str, Any]],
#     ]:

#         merged_concepts: Dict[
#             str,
#             Dict[str, Any],
#         ] = {}

#         # ------------------------------------------------------------------
#         # PASS 1
#         # CONCEPT DEDUPLICATION
#         # ------------------------------------------------------------------

#         for raw_concept in raw_concepts:

#             if not isinstance(
#                 raw_concept,
#                 dict,
#             ):
#                 continue

#             concept = dict(
#                 raw_concept
#             )

#             concept_name = str(
#                 concept.get(
#                     "canonical_name",
#                     "",
#                 )
#                 or ""
#             ).strip()

#             if not concept_name:
#                 continue

#             if self._is_metadata_concept(
#                 concept_name
#             ):
#                 continue

#             key = self._normalize_key(
#                 concept_name
#             )

#             if key == "unknown":
#                 continue

#             # --------------------------------------------------------------
#             # Ensure category is valid.
#             # --------------------------------------------------------------

#             category = concept.get(
#                 "category"
#             )

#             if (
#                 category
#                 and category
#                 not in self.ontology_categories
#             ):

#                 concept[
#                     "category"
#                 ] = "Entity"

#             # --------------------------------------------------------------
#             # Normalize lists.
#             # --------------------------------------------------------------

#             synonyms = concept.get(
#                 "synonyms",
#                 [],
#             )

#             if not isinstance(
#                 synonyms,
#                 list,
#             ):
#                 synonyms = [str(synonyms)]

#             keywords = concept.get(
#                 "keywords",
#                 [],
#             )

#             if not isinstance(
#                 keywords,
#                 list,
#             ):
#                 keywords = [str(keywords)]

#             concept[
#                 "synonyms"
#             ] = sorted(
#                 {
#                     str(value).strip()
#                     for value in synonyms
#                     if str(value).strip()
#                 }
#             )

#             concept[
#                 "keywords"
#             ] = sorted(
#                 {
#                     str(value).strip()
#                     for value in keywords
#                     if str(value).strip()
#                 }
#             )[:10]

#             # --------------------------------------------------------------
#             # MERGE
#             # --------------------------------------------------------------

#             if key not in merged_concepts:

#                 concept[
#                     "canonical_name"
#                 ] = concept_name

#                 merged_concepts[
#                     key
#                 ] = concept

#                 continue

#             existing = (
#                 merged_concepts[key]
#             )

#             # --------------------------------------------------------------
#             # SYNONYMS
#             # --------------------------------------------------------------

#             existing_synonyms = set(
#                 existing.get(
#                     "synonyms",
#                     [],
#                 )
#             )

#             existing_synonyms.update(
#                 concept.get(
#                     "synonyms",
#                     [],
#                 )
#             )

#             existing[
#                 "synonyms"
#             ] = sorted(
#                 existing_synonyms
#             )

#             # --------------------------------------------------------------
#             # KEYWORDS
#             # --------------------------------------------------------------

#             existing_keywords = set(
#                 existing.get(
#                     "keywords",
#                     [],
#                 )
#             )

#             existing_keywords.update(
#                 concept.get(
#                     "keywords",
#                     [],
#                 )
#             )

#             existing[
#                 "keywords"
#             ] = sorted(
#                 existing_keywords
#             )[:10]

#             # --------------------------------------------------------------
#             # HIERARCHY
#             # --------------------------------------------------------------

#             current_hierarchy = str(
#                 concept.get(
#                     "hierarchy_context",
#                     "",
#                 )
#                 or ""
#             ).strip()

#             existing_hierarchy = str(
#                 existing.get(
#                     "hierarchy_context",
#                     "",
#                 )
#                 or ""
#             ).strip()

#             if (
#                 current_hierarchy
#                 and current_hierarchy
#                 not in existing_hierarchy
#             ):

#                 if existing_hierarchy:

#                     existing[
#                         "hierarchy_context"
#                     ] = (
#                         existing_hierarchy
#                         + " | "
#                         + current_hierarchy
#                     )

#                 else:

#                     existing[
#                         "hierarchy_context"
#                     ] = current_hierarchy

#         # ------------------------------------------------------------------
#         # PASS 2
#         # RELATIONSHIP VALIDATION
#         # ------------------------------------------------------------------

#         valid_keys = set(
#             merged_concepts.keys()
#         )

#         clean_relationships = []

#         seen_relationships = set()

#         for raw_relationship in (
#             raw_relationships
#         ):

#             if not isinstance(
#                 raw_relationship,
#                 dict,
#             ):
#                 continue

#             relationship = dict(
#                 raw_relationship
#             )

#             source_name = str(
#                 relationship.get(
#                     "source_concept",
#                     "",
#                 )
#                 or ""
#             ).strip()

#             target_name = str(
#                 relationship.get(
#                     "target_concept",
#                     "",
#                 )
#                 or ""
#             ).strip()

#             source_key = (
#                 self._normalize_key(
#                     source_name
#                 )
#             )

#             target_key = (
#                 self._normalize_key(
#                     target_name
#                 )
#             )

#             # --------------------------------------------------------------
#             # Both concepts must exist.
#             # --------------------------------------------------------------

#             if (
#                 source_key
#                 not in valid_keys
#                 or target_key
#                 not in valid_keys
#             ):
#                 continue

#             # --------------------------------------------------------------
#             # Prevent self loops.
#             # --------------------------------------------------------------

#             if source_key == target_key:
#                 continue

#             relationship_type = str(
#                 relationship.get(
#                     "relationship_type",
#                     "related_to",
#                 )
#                 or "related_to"
#             ).strip()

#             if not relationship_type:
#                 relationship_type = (
#                     "related_to"
#                 )

#             # --------------------------------------------------------------
#             # Canonical names
#             # --------------------------------------------------------------

#             relationship[
#                 "source_concept"
#             ] = merged_concepts[
#                 source_key
#             ][
#                 "canonical_name"
#             ]

#             relationship[
#                 "target_concept"
#             ] = merged_concepts[
#                 target_key
#             ][
#                 "canonical_name"
#             ]

#             relationship[
#                 "relationship_type"
#             ] = relationship_type

#             # --------------------------------------------------------------
#             # Deduplicate
#             # --------------------------------------------------------------

#             signature = (
#                 f"{source_key}:::"
#                 f"{relationship_type}:::"
#                 f"{target_key}"
#             )

#             if signature in (
#                 seen_relationships
#             ):
#                 continue

#             seen_relationships.add(
#                 signature
#             )

#             clean_relationships.append(
#                 relationship
#             )

#         return (
#             list(
#                 merged_concepts.values()
#             ),
#             clean_relationships,
#         )

#     # ======================================================================
#     # METADATA READ
#     # ======================================================================

#     def _read_metadata(
#         self,
#         metadata_path: Path,
#     ) -> Dict[str, Any]:

#         if not metadata_path.exists():
#             return {}

#         try:

#             with open(
#                 metadata_path,
#                 "r",
#                 encoding="utf-8",
#             ) as file:

#                 value = json.load(file)

#                 if isinstance(
#                     value,
#                     dict,
#                 ):
#                     return value

#         except Exception as exc:

#             logger.warning(
#                 f"Could not read metadata "
#                 f"{metadata_path}: {exc}"
#             )

#         return {}

#     # ======================================================================
#     # ATOMIC JSON WRITE
#     # ======================================================================

#     def _atomic_write_json(
#         self,
#         path: Path,
#         data: Dict[str, Any],
#     ) -> None:

#         path.parent.mkdir(
#             parents=True,
#             exist_ok=True,
#         )

#         temporary_path = path.with_suffix(
#             path.suffix + ".tmp"
#         )

#         with open(
#             temporary_path,
#             "w",
#             encoding="utf-8",
#         ) as file:

#             json.dump(
#                 data,
#                 file,
#                 indent=4,
#                 ensure_ascii=False,
#             )

#             file.flush()

#         temporary_path.replace(
#             path
#         )

#     # ======================================================================
#     # UPDATE PIPELINE METADATA
#     # ======================================================================

#     def _update_metadata_status(
#         self,
#         metadata_path: Path,
#         document_id: str,
#         status: str,
#     ) -> None:

#         if not metadata_path.exists():
#             return

#         metadata = self._read_metadata(
#             metadata_path
#         )

#         if not metadata:
#             return

#         metadata[
#             "pipeline_status"
#         ] = status

#         if status == "KNOWLEDGE_EXTRACTED":

#             metadata[
#                 "next_step"
#             ] = (
#                 f"{settings.API_V1_STR}"
#                 f"/documents/{document_id}"
#                 f"/knowledge"
#             )

#         elif status == "KNOWLEDGE_EXTRACTION_FAILED":

#             metadata[
#                 "next_step"
#             ] = None

#         try:

#             self._atomic_write_json(
#                 metadata_path,
#                 metadata,
#             )

#         except Exception as exc:

#             logger.warning(
#                 f"Could not update metadata "
#                 f"for {document_id}: {exc}"
#             )

#     # ======================================================================
#     # MASTER PIPELINE
#     # ======================================================================

#     async def extract_knowledge(
#         self,
#         document_id: str,
#     ) -> Dict[str, Any]:

#         started_at = (
#             time.perf_counter()
#         )

#         processed_base = (
#             self.processed_dir
#             / document_id
#         )

#         normalized_path = (
#             processed_base
#             / "normalized_elements.jsonl"
#         )

#         metadata_path = (
#             self.raw_dir
#             / document_id
#             / "metadata.json"
#         )

#         extracted_knowledge_path = (
#             processed_base
#             / "extracted_knowledge.json"
#         )

#         logger.info(
#             f"Starting TagTaste sensory "
#             f"knowledge extraction "
#             f"for {document_id}"
#         )

#         try:

#             # ==============================================================
#             # 1. WAIT FOR STRUCTURAL EXTRACTION
#             # ==============================================================

#             await self._wait_for_normalized_file(
#                 normalized_path,
#                 document_id,
#             )

#             # ==============================================================
#             # 2. DOCUMENT METADATA
#             # ==============================================================

#             metadata = self._read_metadata(
#                 metadata_path
#             )

#             book_title = metadata.get(
#                 "title",
#                 "Scientific Document",
#             )

#             # ==============================================================
#             # 3. LOAD NORMALIZED ELEMENTS
#             # ==============================================================

#             elements = (
#                 self._load_normalized_elements(
#                     normalized_path
#                 )
#             )

#             if not elements:

#                 logger.warning(
#                     f"No normalized elements found "
#                     f"for {document_id}"
#                 )

#                 empty_result = {
#                     "document_id": document_id,
#                     "pipeline_status": (
#                         "KNOWLEDGE_EXTRACTED"
#                     ),
#                     "extracted_stats": {
#                         "raw_concepts_found": 0,
#                         "clean_concepts_saved": 0,
#                         "relationships_extracted": 0,
#                     },
#                     "knowledge_artifact_path": str(
#                         extracted_knowledge_path.relative_to(
#                             settings.BASE_DIR
#                         )
#                     ),
#                 }

#                 self._atomic_write_json(
#                     extracted_knowledge_path,
#                     {
#                         "document_id": document_id,
#                         "concepts": [],
#                         "relationships": [],
#                         "scientific_rules": [],
#                         "procedures": [],
#                     },
#                 )

#                 self._update_metadata_status(
#                     metadata_path,
#                     document_id,
#                     "KNOWLEDGE_EXTRACTED",
#                 )

#                 return empty_result

#             logger.info(
#                 f"Loaded {len(elements)} "
#                 f"normalized elements "
#                 f"for {document_id}"
#             )

#             # ==============================================================
#             # 4. PRE-CACHE
#             # ==============================================================

#             cache_start = (
#                 time.perf_counter()
#             )

#             self._prepare_element_cache(
#                 elements
#             )

#             logger.info(
#                 f"Element cache prepared for "
#                 f"{document_id} in "
#                 f"{time.perf_counter() - cache_start:.2f}s"
#             )

#             # ==============================================================
#             # 5. BUILD LOGICAL UNITS
#             # ==============================================================

#             split_start = (
#                 time.perf_counter()
#             )

#             logical_units = (
#                 self._hierarchical_split(
#                     elements,
#                     book_title,
#                     depth=0,
#                 )
#             )

#             split_elapsed = (
#                 time.perf_counter()
#                 - split_start
#             )

#             total_units = len(
#                 logical_units
#             )

#             logger.info(
#                 f"Created {total_units} "
#                 f"logical sensory units "
#                 f"for {document_id} "
#                 f"in {split_elapsed:.2f}s. "
#                 f"Concurrency="
#                 f"{self.max_concurrent_requests}"
#             )

#             # ==============================================================
#             # 6. CONCURRENT LLM EXTRACTION
#             # ==============================================================

#             semaphore = asyncio.Semaphore(
#                 self.max_concurrent_requests
#             )

#             async def bounded_process(
#                 unit_index: int,
#                 unit_data: Dict[str, Any],
#             ):

#                 async with semaphore:

#                     try:

#                         return await (
#                             self._process_logical_unit(
#                                 f"unit_{unit_index}",
#                                 unit_data,
#                             )
#                         )

#                     except Exception as exc:

#                         logger.error(
#                             f"Unexpected extraction "
#                             f"failure in unit "
#                             f"{unit_index}: "
#                             f"{exc}",
#                             exc_info=True,
#                         )

#                         return (
#                             self._empty_extraction()
#                         )

#             tasks = [
#                 asyncio.create_task(
#                     bounded_process(
#                         index,
#                         unit,
#                     )
#                 )
#                 for index, unit
#                 in enumerate(
#                     logical_units
#                 )
#             ]

#             raw_concepts = []

#             raw_relationships = []

#             scientific_rules = []

#             procedures = []

#             completed = 0

#             llm_start = (
#                 time.perf_counter()
#             )

#             # --------------------------------------------------------------
#             # Consume results as soon as they finish.
#             # --------------------------------------------------------------

#             for completed_task in (
#                 asyncio.as_completed(
#                     tasks
#                 )
#             ):

#                 try:

#                     result = await (
#                         completed_task
#                     )

#                 except Exception as exc:

#                     logger.error(
#                         f"Logical unit failed "
#                         f"for {document_id}: "
#                         f"{exc}",
#                         exc_info=True,
#                     )

#                     result = (
#                         self._empty_extraction()
#                     )

#                 completed += 1

#                 raw_concepts.extend(
#                     result.get(
#                         "concepts",
#                         [],
#                     )
#                 )

#                 raw_relationships.extend(
#                     result.get(
#                         "relationships",
#                         [],
#                     )
#                 )

#                 scientific_rules.extend(
#                     result.get(
#                         "scientific_rules",
#                         [],
#                     )
#                 )

#                 procedures.extend(
#                     result.get(
#                         "procedures",
#                         [],
#                     )
#                 )

#                 logger.debug(
#                     f"Knowledge extraction "
#                     f"progress for "
#                     f"{document_id}: "
#                     f"{completed}/"
#                     f"{total_units}"
#                 )

#             llm_elapsed = (
#                 time.perf_counter()
#                 - llm_start
#             )

#             logger.info(
#                 f"LLM sensory extraction "
#                 f"completed for "
#                 f"{document_id} in "
#                 f"{llm_elapsed:.2f}s"
#             )

#             # ==============================================================
#             # 7. GLOBAL GRAPH STITCHING
#             # ==============================================================

#             stitch_start = (
#                 time.perf_counter()
#             )

#             (
#                 clean_concepts,
#                 clean_relationships,
#             ) = self._stitch_global_graph(
#                 raw_concepts,
#                 raw_relationships,
#             )

#             stitch_elapsed = (
#                 time.perf_counter()
#                 - stitch_start
#             )

#             logger.info(
#                 f"Global sensory graph "
#                 f"stitching completed for "
#                 f"{document_id} in "
#                 f"{stitch_elapsed:.2f}s"
#             )

#             # ==============================================================
#             # 8. BUILD FINAL ARTIFACT
#             # ==============================================================

#             master_knowledge = {
#                 "document_id": document_id,

#                 "concepts": clean_concepts,

#                 "relationships": clean_relationships,

#                 "scientific_rules": (
#                     scientific_rules
#                 ),

#                 "procedures": procedures,
#             }

#             # ==============================================================
#             # 9. ATOMIC SAVE
#             # ==============================================================

#             self._atomic_write_json(
#                 extracted_knowledge_path,
#                 master_knowledge,
#             )

#             # ==============================================================
#             # 10. UPDATE PIPELINE STATUS
#             # ==============================================================

#             self._update_metadata_status(
#                 metadata_path,
#                 document_id,
#                 "KNOWLEDGE_EXTRACTED",
#             )

#             # ==============================================================
#             # 11. FINAL RESPONSE
#             # ==============================================================

#             total_elapsed = (
#                 time.perf_counter()
#                 - started_at
#             )

#             logger.info(
#                 f"TagTaste sensory knowledge "
#                 f"extraction completed for "
#                 f"{document_id} in "
#                 f"{total_elapsed:.2f}s. "
#                 f"Raw concepts="
#                 f"{len(raw_concepts)}, "
#                 f"Clean concepts="
#                 f"{len(clean_concepts)}, "
#                 f"Relationships="
#                 f"{len(clean_relationships)}"
#             )

#             # IMPORTANT:
#             # Keep existing API response shape.

#             return {
#                 "document_id": document_id,
#                 "pipeline_status": (
#                     "KNOWLEDGE_EXTRACTED"
#                 ),
#                 "extracted_stats": {
#                     "raw_concepts_found": len(
#                         raw_concepts
#                     ),
#                     "clean_concepts_saved": len(
#                         clean_concepts
#                     ),
#                     "relationships_extracted": len(
#                         clean_relationships
#                     ),
#                 },
#                 "knowledge_artifact_path": str(
#                     extracted_knowledge_path.relative_to(
#                         settings.BASE_DIR
#                     )
#                 ),
#             }

#         except (
#             DocumentNotFoundError,
#             ProcessingError,
#         ):

#             # --------------------------------------------------------------
#             # DO NOT let these exceptions escape from a background task.
#             # --------------------------------------------------------------

#             logger.error(
#                 f"Knowledge extraction could not "
#                 f"start for {document_id}",
#                 exc_info=True,
#             )

#             self._update_metadata_status(
#                 metadata_path,
#                 document_id,
#                 "KNOWLEDGE_EXTRACTION_FAILED",
#             )

#             # --------------------------------------------------------------
#             # IMPORTANT:
#             #
#             # Returning a controlled result prevents:
#             #
#             # RuntimeError:
#             # Caught handled exception, but response
#             # already started.
#             # --------------------------------------------------------------

#             return {
#                 "document_id": document_id,
#                 "pipeline_status": (
#                     "KNOWLEDGE_EXTRACTION_FAILED"
#                 ),
#                 "extracted_stats": {
#                     "raw_concepts_found": 0,
#                     "clean_concepts_saved": 0,
#                     "relationships_extracted": 0,
#                 },
#                 "knowledge_artifact_path": None,
#             }

#         except Exception as exc:

#             logger.error(
#                 f"Knowledge extraction failed "
#                 f"for {document_id}: "
#                 f"{exc}",
#                 exc_info=True,
#             )

#             self._update_metadata_status(
#                 metadata_path,
#                 document_id,
#                 "KNOWLEDGE_EXTRACTION_FAILED",
#             )

#             # --------------------------------------------------------------
#             # IMPORTANT:
#             # Background task must not raise after 202 response.
#             # --------------------------------------------------------------

#             return {
#                 "document_id": document_id,
#                 "pipeline_status": (
#                     "KNOWLEDGE_EXTRACTION_FAILED"
#                 ),
#                 "extracted_stats": {
#                     "raw_concepts_found": 0,
#                     "clean_concepts_saved": 0,
#                     "relationships_extracted": 0,
#                 },
#                 "knowledge_artifact_path": None,
#             }











# import asyncio
# import json
# import re
# import time
# from pathlib import Path
# from typing import Any, Dict, List, Optional, Set, Tuple

# from openai import AsyncOpenAI

# try:
#     import tiktoken

#     _TOKENIZER = tiktoken.get_encoding("cl100k_base")

#     def count_tokens(text: str) -> int:
#         if not text:
#             return 0
#         return len(_TOKENIZER.encode(text))

# except ImportError:

#     def count_tokens(text: str) -> int:
#         if not text:
#             return 0
#         return max(1, len(text) // 4)


# from app.core.config import settings
# from app.core.exceptions import (
#     DocumentNotFoundError,
#     ProcessingError,
#     StorageError,
# )
# from app.core.logger import logger
# from app.models.knowledge import KnowledgeExtractionPayload


# class KnowledgeService:
#     """
#     TagTaste Sensory Knowledge Extraction Service.

#     Pipeline:

#         PDF
#           |
#           v
#         Structural extraction
#           |
#           v
#         normalized_elements.jsonl
#           |
#           v
#         hierarchy-aware sensory chunking
#           |
#           v
#         concurrent structured LLM extraction
#           |
#           v
#         deterministic sensory validation
#           |
#           v
#         global graph stitching
#           |
#           v
#         extracted_knowledge.json

#     Main goals:

#     1. Preserve existing API response shape.
#     2. Preserve complete sensory context.
#     3. Preserve product/sample/attribute/value relationships.
#     4. Preserve table semantics.
#     5. Preserve hierarchy and provenance.
#     6. Prevent floating numeric concepts.
#     7. Prevent citation/bibliographic noise.
#     8. Validate relationship types.
#     9. Deduplicate concepts safely.
#     10. Deduplicate scientific rules and procedures.
#     11. Retry transient LLM failures.
#     12. Prevent background-task exceptions from escaping.
#     13. Keep deterministic post-processing.
#     """

#     # ==================================================================
#     # CONSTANTS
#     # ==================================================================

#     DEFAULT_MODEL = "gpt-4o-mini"

#     DEFAULT_MAX_CONCURRENT_REQUESTS = 10

#     # Keep enough context for tables + hierarchy + sensory relationships.
#     MAX_TOKENS_PER_CHUNK = 6000

#     # Previous elements carried into next linear chunk.
#     OVERLAP_ELEMENTS = 3

#     MIN_PAYLOAD_LENGTH = 100

#     # --------------------------------------------------------------
#     # Structural extraction synchronization
#     # --------------------------------------------------------------

#     NORMALIZED_FILE_WAIT_SECONDS = 90.0
#     NORMALIZED_FILE_POLL_INTERVAL = 0.50
#     NORMALIZED_FILE_STABLE_CHECKS = 2

#     # --------------------------------------------------------------
#     # LLM
#     # --------------------------------------------------------------

#     LLM_MAX_RETRIES = 2
#     LLM_RETRY_BASE_DELAY = 0.75

#     # --------------------------------------------------------------
#     # Metadata / bibliographic filtering
#     # --------------------------------------------------------------

#     METADATA_KEYWORDS = {
#         "press",
#         "isbn",
#         "copyright",
#         "edition",
#         "publisher",
#         "bibliography",
#         "reference",
#         "references",
#         "printing",
#         "printed",
#         "catalog",
#         "catalogue",
#     }

#     # Citation patterns such as:
#     #
#     # Bartoshuk 1978
#     # Pangborn 1984
#     # Smith et al. 2019
#     #
#     CITATION_PATTERNS = [
#         re.compile(
#             r"^[A-Z][A-Za-z'`\-]+(?:\s+et\s+al\.)?\s+\d{4}$"
#         ),
#         re.compile(
#             r"^[A-Z][A-Za-z'`\-]+(?:\s*&\s*[A-Z][A-Za-z'`\-]+)?\s+\(\d{4}\)$"
#         ),
#         re.compile(
#             r"^\d{4}$"
#         ),
#     ]

#     # --------------------------------------------------------------
#     # Numeric / measurement patterns
#     # --------------------------------------------------------------

#     NUMERIC_ONLY_PATTERN = re.compile(
#         r"^[\s\+\-−]?"
#         r"\d+(?:[.,]\d+)?"
#         r"(?:\s*[%°])?"
#         r"(?:\s*[A-Za-z]+)?"
#         r"$"
#     )

#     SCORE_PATTERN = re.compile(
#         r"^(?:score|rating|value|measurement|intensity)"
#         r"(?:\s*[:=])?\s*[\d.,]+",
#         re.IGNORECASE,
#     )

#     # --------------------------------------------------------------
#     # Sensory vocabulary
#     # --------------------------------------------------------------

#     SENSORY_ATTRIBUTE_TERMS = {
#         "appearance",
#         "aroma",
#         "odor",
#         "odour",
#         "flavor",
#         "flavour",
#         "taste",
#         "mouthfeel",
#         "texture",
#         "aftertaste",
#         "finish",
#         "overall liking",
#         "liking",
#         "acceptability",
#         "sweetness",
#         "sourness",
#         "bitterness",
#         "saltiness",
#         "umami",
#         "astringency",
#         "acidity",
#         "spiciness",
#         "heat",
#         "freshness",
#         "intensity",
#         "color",
#         "colour",
#         "opacity",
#         "clarity",
#         "viscosity",
#         "creaminess",
#         "crispness",
#         "crunchiness",
#         "hardness",
#         "softness",
#         "chewiness",
#         "juiciness",
#         "tenderness",
#         "thickness",
#         "coating",
#         "persistence",
#         "balance",
#     }

#     # Words that are commonly descriptors/intensity values rather than
#     # standalone sensory attributes.
#     DESCRIPTOR_TERMS = {
#         "strong",
#         "weak",
#         "mild",
#         "moderate",
#         "high",
#         "low",
#         "intense",
#         "slight",
#         "slightly",
#         "pronounced",
#         "subtle",
#         "fresh",
#         "stale",
#         "crisp",
#         "crunchy",
#         "soft",
#         "hard",
#         "smooth",
#         "rough",
#         "creamy",
#         "thick",
#         "thin",
#         "bitter",
#         "sweet",
#         "salty",
#         "sour",
#         "spicy",
#         "astringent",
#     }

#     # ==================================================================
#     # INITIALIZATION
#     # ==================================================================

#     def __init__(self):

#         self.raw_dir = Path(
#             settings.STORAGE_RAW_DIR
#         )

#         self.processed_dir = Path(
#             settings.STORAGE_PROCESSED_DIR
#         )

#         # --------------------------------------------------------------
#         # Long-lived OpenAI client
#         # --------------------------------------------------------------

#         self.client = AsyncOpenAI(
#             api_key=settings.OPENAI_API_KEY,
#             timeout=getattr(
#                 settings,
#                 "OPENAI_TIMEOUT",
#                 120.0,
#             ),
#             max_retries=getattr(
#                 settings,
#                 "OPENAI_MAX_RETRIES",
#                 2,
#             ),
#         )

#         # --------------------------------------------------------------
#         # Model
#         # --------------------------------------------------------------

#         self.model_name = getattr(
#             settings,
#             "OPENAI_KNOWLEDGE_MODEL",
#             self.DEFAULT_MODEL,
#         )

#         # --------------------------------------------------------------
#         # Concurrency
#         # --------------------------------------------------------------

#         configured_concurrency = getattr(
#             settings,
#             "MAX_CONCURRENT_EXTRACTIONS",
#             self.DEFAULT_MAX_CONCURRENT_REQUESTS,
#         )

#         try:
#             configured_concurrency = int(
#                 configured_concurrency
#             )
#         except (
#             TypeError,
#             ValueError,
#         ):
#             configured_concurrency = (
#                 self.DEFAULT_MAX_CONCURRENT_REQUESTS
#             )

#         self.max_concurrent_requests = max(
#             1,
#             configured_concurrency,
#         )

#         # --------------------------------------------------------------
#         # Chunking
#         # --------------------------------------------------------------

#         self.max_tokens_per_chunk = (
#             self.MAX_TOKENS_PER_CHUNK
#         )

#         self.overlap_elements = (
#             self.OVERLAP_ELEMENTS
#         )

#         # --------------------------------------------------------------
#         # Ontology
#         # --------------------------------------------------------------

#         self.ontology_categories = [
#             "Entity",
#             "Method",
#             "Theory",
#             "Process",
#             "Material",
#             "Chemical",
#             "Instrument",
#             "Organization",
#             "Measurement",
#             "Property",
#             "Sensory_Attribute",
#         ]

#         # --------------------------------------------------------------
#         # Relationship vocabulary
#         # --------------------------------------------------------------

#         self.sensory_relationships = [
#             "has_sensory_attribute",
#             "has_descriptor",
#             "has_intensity",
#             "has_score",
#             "uses_scale",
#             "measured_by",
#             "evaluated_by",
#             "compared_with",
#             "benchmarked_against",
#             "prepared_by",
#             "contains",
#             "derived_from",
#             "belongs_to",
#             "part_of",
#             "associated_with",
#             "caused_by",
#             "influences",
#             "correlates_with",
#             "defined_by",
#             "measured_under",
#             "tested_by",
#             "has_method",
#             "has_property",
#             "related_to",
#         ]

#         self.allowed_relationships = set(
#             self.sensory_relationships
#         )

#         # --------------------------------------------------------------
#         # Per-document cache
#         # --------------------------------------------------------------

#         self._element_text_cache: Dict[int, str] = {}
#         self._element_token_cache: Dict[int, int] = {}

#         # --------------------------------------------------------------
#         # Static system prompt
#         # --------------------------------------------------------------

#         self._system_prompt = (
#             self._build_system_prompt()
#         )

#     # ==================================================================
#     # EMPTY RESULT
#     # ==================================================================

#     @staticmethod
#     def _empty_extraction() -> Dict[str, List[Any]]:
#         return {
#             "concepts": [],
#             "relationships": [],
#             "scientific_rules": [],
#             "procedures": [],
#         }

#     # ==================================================================
#     # SYSTEM PROMPT
#     # ==================================================================

#     def _build_system_prompt(self) -> str:

#         ontology = ", ".join(
#             self.ontology_categories
#         )

#         relationship_types = ", ".join(
#             self.sensory_relationships
#         )

#         return f"""
# You are the primary Knowledge Graph extraction engine for TagTaste.

# TagTaste is a sensory intelligence platform.

# Your task is NOT generic keyword extraction.

# Your task is to understand the COMPLETE semantic and sensory context
# contained in technical documents, sensory evaluation documents,
# product documents, food/beverage documents, sensory studies,
# questionnaires, test reports, scientific documents, tables, charts,
# procedures and methodologies.

# Convert explicitly supported document knowledge into a structured
# knowledge graph.

# ============================================================
# ONTOLOGY
# ============================================================

# Every concept category MUST be one of:

# {ontology}

# ============================================================
# IMPORTANT EXTRACTION RULE
# ============================================================

# Extract concepts only when they have meaningful semantic value in the
# document.

# Do NOT create standalone concepts for:

# - raw numbers
# - scores without their measured concept
# - percentages without their measured concept
# - temperatures without their measured concept
# - isolated intensity words
# - isolated table values
# - page numbers
# - figure numbers
# - section numbers
# - citation strings
# - bibliographic references

# For example:

# "Sweetness = 7 on a 9-point scale"

# must preserve the semantic structure:

# Sample
#   -> has_sensory_attribute -> Sweetness
#   -> has_score -> 7
# Sweetness
#   -> uses_scale -> 9-point scale

# The number 7 must NOT become an independent concept.

# ============================================================
# SENSORY ATTRIBUTES
# ============================================================

# Understand concepts such as:

# appearance
# aroma
# odor
# flavor
# taste
# mouthfeel
# texture
# aftertaste
# finish
# overall liking
# acceptability
# sweetness
# sourness
# bitterness
# saltiness
# umami
# astringency
# acidity
# spiciness
# heat
# freshness
# intensity
# color
# opacity
# clarity
# viscosity
# creaminess
# crispness
# crunchiness
# hardness
# softness
# chewiness
# juiciness
# tenderness
# thickness
# coating
# persistence
# balance

# This is NOT an exhaustive vocabulary.

# If another sensory attribute is explicitly present, extract it.

# ============================================================
# SENSORY CONTEXT
# ============================================================

# Preserve:

# - product/sample identity
# - product formulation
# - batch
# - treatment
# - benchmark/reference
# - sensory domain
# - sensory attribute
# - descriptor
# - intensity
# - score
# - rating
# - scale
# - scale endpoints
# - preparation method
# - serving condition
# - evaluation method
# - panel/test context
# - ingredient/material
# - chemical
# - instrument
# - measurement
# - analysis method

# Never flatten these into unrelated keywords.

# ============================================================
# TABLE SEMANTICS
# ============================================================

# Tables are extremely important.

# For:

# Product | Sweetness | Bitterness | Aroma
# Sample A | 7 | 2 | 8

# the semantic interpretation is:

# Sample A
#   -> Sweetness = 7
#   -> Bitterness = 2
#   -> Aroma = 8

# The numeric values must remain attached to the correct row and column.

# For:

# Descriptor | Intensity
# Vanilla | Strong

# preserve:

# Vanilla
#   -> has_intensity -> Strong

# Do NOT create a floating concept named "Strong".

# ============================================================
# MEASUREMENTS
# ============================================================

# Preserve:

# - score
# - rating
# - intensity
# - concentration
# - percentage
# - temperature
# - pH
# - viscosity
# - time
# - duration
# - average
# - median
# - standard deviation
# - minimum
# - maximum
# - measurement
# - scale

# Example:

# "pH 4.2"

# means:

# pH
#   -> has_score/measurement relationship
#   -> 4.2

# Do not invent a relationship when the schema does not explicitly
# support it.

# Prefer an appropriate Measurement concept only when the document
# clearly identifies the measurement.

# ============================================================
# HIERARCHY
# ============================================================

# Input contains markers such as:

# --- HIERARCHY: Chapter > Sensory Evaluation > Flavor ---

# Use the complete hierarchy context.

# Populate hierarchy_context.

# Do not discard section information.

# ============================================================
# PROVENANCE
# ============================================================

# Use the supplied page number and element id.

# If the concept occurs in a table, preserve the table element context.

# Do not invent page numbers.

# ============================================================
# PRODUCT / SAMPLE DISTINCTION
# ============================================================

# Preserve the distinction between:

# - product
# - sample
# - formulation
# - treatment
# - batch
# - benchmark
# - reference
# - control

# Do not merge different samples simply because their names are similar.

# ============================================================
# RELATIONSHIPS
# ============================================================

# Allowed relationship types:

# {relationship_types}

# Every relationship must be explicitly supported by the supplied text.

# If no precise relationship is appropriate, use:

# related_to

# Do not invent relationship names.

# Examples:

# Sample A
#   -> compared_with -> Brand B

# Sample A
#   -> has_sensory_attribute -> Sweetness

# Sample A
#   -> evaluated_by -> Hedonic Scale

# ============================================================
# CITATIONS
# ============================================================

# Do NOT extract bibliographic citations as domain concepts.

# Examples that should normally NOT become concepts:

# Bartoshuk 1978
# Pangborn 1984
# Smith et al. 2019

# unless the document explicitly discusses the study itself as domain
# knowledge.

# ============================================================
# NO INFERENCE
# ============================================================

# Use ONLY information explicitly supported by the supplied document.

# Never:

# - invent sensory attributes
# - infer causes
# - infer ingredients
# - infer scientific relationships
# - invent score ranges
# - invent benchmark products
# - infer meanings solely because they seem scientifically plausible
# - merge concepts merely because their names look similar

# ============================================================
# OUTPUT
# ============================================================

# Return ONLY the structured output defined by:

# KnowledgeExtractionPayload

# Do not return markdown.
# Do not return explanations.
# Do not return analysis.
# Do not return commentary.
# """

#     # ==================================================================
#     # TABLE RENDERING
#     # ==================================================================

#     def _render_table_markdown(
#         self,
#         cells: List[Dict],
#     ) -> str:

#         if not cells:
#             return ""

#         max_row = -1
#         max_col = -1

#         for cell in cells:

#             row_idx = cell.get(
#                 "row_idx",
#                 0,
#             )

#             col_idx = cell.get(
#                 "col_idx",
#                 0,
#             )

#             try:
#                 row_idx = int(row_idx)
#                 col_idx = int(col_idx)
#             except (
#                 TypeError,
#                 ValueError,
#             ):
#                 continue

#             max_row = max(
#                 max_row,
#                 row_idx,
#             )

#             max_col = max(
#                 max_col,
#                 col_idx,
#             )

#         if (
#             max_row < 0
#             or max_col < 0
#         ):
#             return ""

#         grid = [
#             ["" for _ in range(max_col + 1)]
#             for _ in range(max_row + 1)
#         ]

#         for cell in cells:

#             try:
#                 row_idx = int(
#                     cell.get(
#                         "row_idx",
#                         0,
#                     )
#                 )

#                 col_idx = int(
#                     cell.get(
#                         "col_idx",
#                         0,
#                     )
#                 )
#             except (
#                 TypeError,
#                 ValueError,
#             ):
#                 continue

#             if (
#                 0 <= row_idx <= max_row
#                 and 0 <= col_idx <= max_col
#             ):

#                 value = str(
#                     cell.get(
#                         "text",
#                         "",
#                     )
#                     or ""
#                 )

#                 value = (
#                     value
#                     .replace("\n", " ")
#                     .replace("|", "/")
#                     .strip()
#                 )

#                 grid[row_idx][col_idx] = value

#         lines = []

#         for row_idx, row in enumerate(grid):

#             lines.append(
#                 "| "
#                 + " | ".join(row)
#                 + " |"
#             )

#             if row_idx == 0:

#                 lines.append(
#                     "|"
#                     + "|".join(
#                         ["---"] * len(row)
#                     )
#                     + "|"
#                 )

#         return "\n".join(lines)

#     # ==================================================================
#     # ELEMENT TEXT
#     # ==================================================================

#     def _get_element_text(
#         self,
#         element: Dict,
#     ) -> str:

#         cache_key = id(element)

#         cached = self._element_text_cache.get(
#             cache_key
#         )

#         if cached is not None:
#             return cached

#         if element.get("type") == "table":

#             text = self._render_table_markdown(
#                 element.get(
#                     "cells",
#                     [],
#                 )
#             )

#         else:

#             text = str(
#                 element.get(
#                     "text",
#                     "",
#                 )
#                 or ""
#             )

#         self._element_text_cache[
#             cache_key
#         ] = text

#         return text

#     # ==================================================================
#     # TOKEN COUNT
#     # ==================================================================

#     def _get_element_tokens(
#         self,
#         element: Dict,
#     ) -> int:

#         cache_key = id(element)

#         cached = self._element_token_cache.get(
#             cache_key
#         )

#         if cached is not None:
#             return cached

#         tokens = count_tokens(
#             self._get_element_text(element)
#         )

#         self._element_token_cache[
#             cache_key
#         ] = tokens

#         return tokens

#     # ==================================================================
#     # WAIT FOR NORMALIZED FILE
#     # ==================================================================

#     async def _wait_for_normalized_file(
#         self,
#         normalized_path: Path,
#         document_id: str,
#     ) -> None:

#         deadline = (
#             time.monotonic()
#             + self.NORMALIZED_FILE_WAIT_SECONDS
#         )

#         last_signature = None
#         stable_count = 0

#         while time.monotonic() < deadline:

#             if normalized_path.exists():

#                 try:

#                     stat = normalized_path.stat()

#                     if stat.st_size <= 0:

#                         stable_count = 0

#                     else:

#                         valid_lines = 0
#                         invalid_lines = 0

#                         with open(
#                             normalized_path,
#                             "r",
#                             encoding="utf-8",
#                         ) as file:

#                             for line_number, line in enumerate(
#                                 file,
#                                 start=1,
#                             ):

#                                 line = line.strip()

#                                 if not line:
#                                     continue

#                                 try:

#                                     json.loads(line)

#                                     valid_lines += 1

#                                 except json.JSONDecodeError:

#                                     invalid_lines += 1

#                                     # Allow one incomplete final line
#                                     # while the producer is still writing.
#                                     if (
#                                         line_number > 1
#                                         and invalid_lines <= 1
#                                     ):
#                                         break

#                         signature = (
#                             stat.st_size,
#                             stat.st_mtime_ns,
#                             valid_lines,
#                         )

#                         if (
#                             valid_lines > 0
#                             and invalid_lines == 0
#                         ):

#                             if signature == last_signature:
#                                 stable_count += 1
#                             else:
#                                 stable_count = 1

#                             last_signature = signature

#                             if (
#                                 stable_count
#                                 >= self.NORMALIZED_FILE_STABLE_CHECKS
#                             ):

#                                 logger.info(
#                                     f"Normalized elements ready "
#                                     f"for {document_id}: "
#                                     f"{valid_lines} records."
#                                 )

#                                 return

#                         else:

#                             stable_count = 0

#                 except (
#                     OSError,
#                     PermissionError,
#                     json.JSONDecodeError,
#                 ) as exc:

#                     logger.debug(
#                         f"Normalized file not readable yet "
#                         f"for {document_id}: {exc}"
#                     )

#             await asyncio.sleep(
#                 self.NORMALIZED_FILE_POLL_INTERVAL
#             )

#         raise ProcessingError(
#             f"Normalized elements are not ready for "
#             f"{document_id} after "
#             f"{self.NORMALIZED_FILE_WAIT_SECONDS:.0f}s. "
#             f"Expected file: {normalized_path}"
#         )

#     # ==================================================================
#     # LOAD NORMALIZED JSONL
#     # ==================================================================

#     def _load_normalized_elements(
#         self,
#         normalized_path: Path,
#     ) -> List[Dict]:

#         elements = []

#         with open(
#             normalized_path,
#             "r",
#             encoding="utf-8",
#         ) as file:

#             for line_number, line in enumerate(
#                 file,
#                 start=1,
#             ):

#                 line = line.strip()

#                 if not line:
#                     continue

#                 try:

#                     value = json.loads(line)

#                     if isinstance(
#                         value,
#                         dict,
#                     ):
#                         elements.append(value)

#                 except json.JSONDecodeError as exc:

#                     logger.warning(
#                         f"Skipping invalid JSONL line "
#                         f"{line_number} in "
#                         f"{normalized_path}: {exc}"
#                     )

#         return elements

#     # ==================================================================
#     # PRE-CACHE
#     # ==================================================================

#     def _prepare_element_cache(
#         self,
#         elements: List[Dict],
#     ) -> None:

#         self._element_text_cache.clear()
#         self._element_token_cache.clear()

#         for element in elements:

#             cache_key = id(element)

#             text = self._get_element_text(
#                 element
#             )

#             self._element_text_cache[
#                 cache_key
#             ] = text

#             self._element_token_cache[
#                 cache_key
#             ] = count_tokens(text)

#     # ==================================================================
#     # HIERARCHY-AWARE CHUNKING
#     # ==================================================================

#     def _hierarchical_split(
#         self,
#         elements: List[Dict],
#         book_title: str,
#         depth: int = 0,
#     ) -> List[Dict]:

#         if not elements:
#             return []

#         total_tokens = sum(
#             self._get_element_tokens(element)
#             for element in elements
#         )

#         if (
#             total_tokens
#             <= self.max_tokens_per_chunk
#         ):

#             return [
#                 {
#                     "book_title": book_title,
#                     "elements": elements,
#                 }
#             ]

#         groups = []
#         current_group = []
#         current_key = None

#         for element in elements:

#             path_nodes = (
#                 element
#                 .get("context", {})
#                 .get("path", [])
#             )

#             path_texts = [
#                 str(
#                     node.get(
#                         "text",
#                         "",
#                     )
#                 )
#                 for node in path_nodes
#             ]

#             if depth < len(path_texts):

#                 key = path_texts[depth]

#             else:

#                 key = ""

#             if (
#                 current_group
#                 and key != current_key
#             ):

#                 groups.append(
#                     current_group
#                 )

#                 current_group = []

#             current_key = key

#             current_group.append(
#                 element
#             )

#         if current_group:

#             groups.append(
#                 current_group
#             )

#         # --------------------------------------------------------------
#         # If hierarchy cannot split further, use linear splitting.
#         # --------------------------------------------------------------

#         if len(groups) == 1:

#             return self._fallback_linear_split(
#                 elements,
#                 book_title,
#             )

#         chunks = []

#         for group in groups:

#             chunks.extend(
#                 self._hierarchical_split(
#                     group,
#                     book_title,
#                     depth + 1,
#                 )
#             )

#         return chunks

#     # ==================================================================
#     # LINEAR FALLBACK SPLIT
#     # ==================================================================

#     def _fallback_linear_split(
#         self,
#         elements: List[Dict],
#         book_title: str,
#     ) -> List[Dict]:

#         chunks = []

#         current_chunk = []
#         current_tokens = 0

#         boundaries = {
#             "paragraph",
#             "heading",
#             "image_occurrence",
#             "table",
#             "caption",
#             "list_item",
#         }

#         for index, element in enumerate(
#             elements
#         ):

#             element_tokens = (
#                 self._get_element_tokens(
#                     element
#                 )
#                 + 15
#             )

#             current_chunk.append(
#                 element
#             )

#             current_tokens += element_tokens

#             is_boundary = (
#                 element.get("type")
#                 in boundaries
#             )

#             should_split = (
#                 current_tokens
#                 >= self.max_tokens_per_chunk
#                 and is_boundary
#                 and index < len(elements) - 1
#             )

#             if should_split:

#                 chunks.append(
#                     {
#                         "book_title": book_title,
#                         "elements": current_chunk,
#                     }
#                 )

#                 overlap_count = min(
#                     self.overlap_elements,
#                     len(current_chunk),
#                 )

#                 overlap = (
#                     current_chunk[
#                         -overlap_count:
#                     ]
#                     if overlap_count
#                     else []
#                 )

#                 current_chunk = (
#                     overlap.copy()
#                 )

#                 current_tokens = sum(
#                     self._get_element_tokens(item)
#                     + 15
#                     for item in current_chunk
#                 )

#         if current_chunk:

#             chunks.append(
#                 {
#                     "book_title": book_title,
#                     "elements": current_chunk,
#                 }
#             )

#         return chunks

#     # ==================================================================
#     # HIERARCHY EXTRACTION
#     # ==================================================================

#     def _get_element_hierarchy(
#         self,
#         element: Dict,
#     ) -> List[str]:

#         path_nodes = (
#             element
#             .get("context", {})
#             .get("path", [])
#         )

#         result = []

#         for node in path_nodes:

#             if isinstance(
#                 node,
#                 dict,
#             ):

#                 value = str(
#                     node.get(
#                         "text",
#                         "",
#                     )
#                     or ""
#                 ).strip()

#             else:

#                 value = str(
#                     node
#                     or ""
#                 ).strip()

#             if value:
#                 result.append(value)

#         return result

#     # ==================================================================
#     # FORMAT LOGICAL PAYLOAD
#     # ==================================================================

#     def _format_logical_payload(
#         self,
#         chunk: Dict[str, Any],
#     ) -> str:

#         book_title = chunk.get(
#             "book_title",
#             "Scientific Document",
#         )

#         elements = chunk.get(
#             "elements",
#             [],
#         )

#         pages = sorted(
#             {
#                 e.get("page_number")
#                 for e in elements
#                 if e.get("page_number")
#                 is not None
#             }
#         )

#         if len(pages) > 1:

#             page_context = (
#                 f"Pages: {pages[0]} - {pages[-1]}"
#             )

#         elif pages:

#             page_context = (
#                 f"Page: {pages[0]}"
#             )

#         else:

#             page_context = ""

#         lines = [
#             "=== TAGTASTE DOCUMENT CONTEXT ===",
#             f"Book: {book_title}",
#             page_context,
#             "",
#             "=== EXTRACTION RULES ===",
#             "Preserve complete semantic relationships.",
#             "Do not create floating numeric concepts.",
#             "Do not create floating descriptors.",
#             "Preserve table row/column semantics.",
#             "Preserve product/sample identity.",
#             "Preserve sensory attribute context.",
#             "Preserve hierarchy.",
#             "Preserve page and element provenance.",
#             "",
#             "=== CONTENT TO EXTRACT ===",
#         ]

#         current_path = None

#         for element in elements:

#             path = tuple(
#                 self._get_element_hierarchy(
#                     element
#                 )
#             )

#             if path != current_path:

#                 hierarchy = (
#                     " > ".join(path)
#                     if path
#                     else "General Content"
#                 )

#                 lines.append(
#                     f"\n--- HIERARCHY: {hierarchy} ---"
#                 )

#                 current_path = path

#             element_type = element.get(
#                 "type",
#                 "paragraph",
#             )

#             page_number = element.get(
#                 "page_number"
#             )

#             element_id = element.get(
#                 "element_id",
#                 "unknown",
#             )

#             # ----------------------------------------------------------
#             # Text-like elements
#             # ----------------------------------------------------------

#             if element_type in {
#                 "heading",
#                 "paragraph",
#                 "caption",
#                 "list_item",
#                 "equation",
#                 "cross_ref",
#                 "raw_text",
#             }:

#                 text_content = str(
#                     element.get(
#                         "text",
#                         "",
#                     )
#                     or ""
#                 ).strip()

#                 if text_content:

#                     lines.append(
#                         f"[{element_type.upper()} "
#                         f"page={page_number} "
#                         f"id={element_id}] "
#                         f"{text_content}"
#                     )

#             # ----------------------------------------------------------
#             # Table
#             # ----------------------------------------------------------

#             elif element_type == "table":

#                 lines.append(
#                     f"[TABLE "
#                     f"page={page_number} "
#                     f"id={element_id}]"
#                 )

#                 table_text = (
#                     self._render_table_markdown(
#                         element.get(
#                             "cells",
#                             [],
#                         )
#                     )
#                 )

#                 if table_text:

#                     lines.append(
#                         table_text
#                     )

#             # ----------------------------------------------------------
#             # Image
#             # ----------------------------------------------------------

#             elif element_type == "image_occurrence":

#                 lines.append(
#                     f"[FIGURE "
#                     f"page={page_number} "
#                     f"id={element_id} "
#                     f"ref={element.get('asset_id', 'unknown')}]"
#                 )

#         return "\n".join(lines)

#     # ==================================================================
#     # CONCEPT PROVENANCE
#     # ==================================================================

#     def _get_chunk_pages(
#         self,
#         elements: List[Dict],
#     ) -> List[Any]:

#         pages = []

#         for element in elements:

#             page = element.get(
#                 "page_number"
#             )

#             if page is not None:
#                 pages.append(page)

#         # Preserve order but remove duplicates.
#         result = []

#         seen = set()

#         for page in pages:

#             key = str(page)

#             if key in seen:
#                 continue

#             seen.add(key)
#             result.append(page)

#         return result

#     # ==================================================================
#     # CONCEPT CLEANUP HELPERS
#     # ==================================================================

#     def _clean_string(
#         self,
#         value: Any,
#     ) -> str:

#         if value is None:
#             return ""

#         return re.sub(
#             r"\s+",
#             " ",
#             str(value),
#         ).strip()

#     def _normalize_key(
#         self,
#         name: str,
#     ) -> str:

#         name = self._clean_string(
#             name
#         )

#         if not name:
#             return "unknown"

#         name = (
#             name
#             .lower()
#             .replace("−", "-")
#         )

#         # Keep word boundaries rather than blindly deleting everything.
#         key = re.sub(
#             r"[^a-z0-9]+",
#             " ",
#             name,
#         ).strip()

#         return key or "unknown"

#     def _is_numeric_only_concept(
#         self,
#         name: str,
#     ) -> bool:

#         name = self._clean_string(
#             name
#         )

#         if not name:
#             return True

#         return bool(
#             self.NUMERIC_ONLY_PATTERN.fullmatch(
#                 name
#             )
#         )

#     def _is_citation_like(
#         self,
#         name: str,
#     ) -> bool:

#         name = self._clean_string(
#             name
#         )

#         if not name:
#             return False

#         for pattern in self.CITATION_PATTERNS:

#             if pattern.fullmatch(name):
#                 return True

#         return False

#     def _is_metadata_concept(
#         self,
#         name: str,
#     ) -> bool:

#         key = self._normalize_key(
#             name
#         )

#         if not key or key == "unknown":
#             return True

#         compact = key.replace(
#             " ",
#             "",
#         )

#         metadata_compact = {
#             keyword.replace(
#                 " ",
#                 "",
#             )
#             for keyword
#             in self.METADATA_KEYWORDS
#         }

#         return any(
#             keyword in compact
#             for keyword
#             in metadata_compact
#         )

#     def _looks_like_descriptor(
#         self,
#         name: str,
#     ) -> bool:

#         key = self._normalize_key(
#             name
#         )

#         return (
#             key in self.DESCRIPTOR_TERMS
#         )

#     def _looks_like_sensory_attribute(
#         self,
#         name: str,
#     ) -> bool:

#         key = self._normalize_key(
#             name
#         )

#         return key in {
#             self._normalize_key(term)
#             for term
#             in self.SENSORY_ATTRIBUTE_TERMS
#         }

#     # ==================================================================
#     # CONCEPT VALIDATION
#     # ==================================================================

#     def _validate_concept(
#         self,
#         concept: Dict[str, Any],
#         chunk_pages: Optional[List[Any]] = None,
#     ) -> Optional[Dict[str, Any]]:

#         concept = dict(
#             concept
#         )

#         concept_name = self._clean_string(
#             concept.get(
#                 "canonical_name",
#                 "",
#             )
#         )

#         if not concept_name:
#             return None

#         # --------------------------------------------------------------
#         # Reject obvious noise.
#         # --------------------------------------------------------------

#         if self._is_numeric_only_concept(
#             concept_name
#         ):
#             return None

#         if self._is_metadata_concept(
#             concept_name
#         ):
#             return None

#         if self._is_citation_like(
#             concept_name
#         ):
#             return None

#         # --------------------------------------------------------------
#         # Category normalization.
#         # --------------------------------------------------------------

#         category = self._clean_string(
#             concept.get(
#                 "category",
#                 "Entity",
#             )
#         )

#         if category not in self.ontology_categories:

#             category = "Entity"

#         # Descriptor protection.
#         #
#         # If LLM calls "Strong" a standalone Entity, reject it.
#         if (
#             self._looks_like_descriptor(
#                 concept_name
#             )
#             and category
#             not in {
#                 "Property",
#                 "Sensory_Attribute",
#             }
#         ):
#             return None

#         # If the name itself is an obvious sensory attribute,
#         # force the appropriate ontology category.
#         if self._looks_like_sensory_attribute(
#             concept_name
#         ):

#             category = "Sensory_Attribute"

#         concept["canonical_name"] = (
#             concept_name
#         )

#         concept["category"] = category

#         # --------------------------------------------------------------
#         # Normalize definition.
#         # --------------------------------------------------------------

#         concept["definition"] = self._clean_string(
#             concept.get(
#                 "definition",
#                 "",
#             )
#         )

#         # --------------------------------------------------------------
#         # Normalize synonyms.
#         # --------------------------------------------------------------

#         synonyms = concept.get(
#             "synonyms",
#             [],
#         )

#         if not isinstance(
#             synonyms,
#             list,
#         ):

#             synonyms = [
#                 synonyms
#             ]

#         cleaned_synonyms = []

#         for value in synonyms:

#             value = self._clean_string(
#                 value
#             )

#             if not value:
#                 continue

#             if value.lower() == concept_name.lower():
#                 continue

#             cleaned_synonyms.append(
#                 value
#             )

#         concept["synonyms"] = sorted(
#             set(cleaned_synonyms)
#         )

#         # --------------------------------------------------------------
#         # Normalize keywords.
#         # --------------------------------------------------------------

#         keywords = concept.get(
#             "keywords",
#             [],
#         )

#         if not isinstance(
#             keywords,
#             list,
#         ):

#             keywords = [
#                 keywords
#             ]

#         cleaned_keywords = []

#         for value in keywords:

#             value = self._clean_string(
#                 value
#             )

#             if value:
#                 cleaned_keywords.append(
#                     value
#                 )

#         concept["keywords"] = sorted(
#             set(cleaned_keywords)
#         )[:20]

#         # --------------------------------------------------------------
#         # Hierarchy context.
#         # --------------------------------------------------------------

#         hierarchy = self._clean_string(
#             concept.get(
#                 "hierarchy_context",
#                 "",
#             )
#         )

#         concept["hierarchy_context"] = (
#             hierarchy
#             or "Extracted Content"
#         )

#         # --------------------------------------------------------------
#         # Source pages.
#         # --------------------------------------------------------------

#         source_pages = concept.get(
#             "source_pages",
#             [],
#         )

#         if not isinstance(
#             source_pages,
#             list,
#         ):

#             source_pages = [
#                 source_pages
#             ]

#         cleaned_pages = []

#         for page in source_pages:

#             if page is None:
#                 continue

#             if page not in cleaned_pages:
#                 cleaned_pages.append(page)

#         if not cleaned_pages and chunk_pages:

#             cleaned_pages = list(
#                 chunk_pages
#             )

#         concept["source_pages"] = (
#             cleaned_pages
#         )

#         # Preserve backwards-compatible source_page.
#         if cleaned_pages:

#             concept["source_page"] = (
#                 cleaned_pages[0]
#             )

#         else:

#             concept["source_page"] = None

#         # --------------------------------------------------------------
#         # Element IDs.
#         # --------------------------------------------------------------

#         element_ids = concept.get(
#             "element_ids",
#             [],
#         )

#         if not isinstance(
#             element_ids,
#             list,
#         ):

#             element_ids = [
#                 element_ids
#             ]

#         concept["element_ids"] = sorted(
#             {
#                 self._clean_string(value)
#                 for value in element_ids
#                 if self._clean_string(value)
#             }
#         )

#         return concept

#     # ==================================================================
#     # RELATIONSHIP VALIDATION
#     # ==================================================================

#     def _validate_relationship(
#         self,
#         relationship: Dict[str, Any],
#     ) -> Optional[Dict[str, Any]]:

#         if not isinstance(
#             relationship,
#             dict,
#         ):
#             return None

#         relationship = dict(
#             relationship
#         )

#         source = self._clean_string(
#             relationship.get(
#                 "source_concept",
#                 "",
#             )
#         )

#         target = self._clean_string(
#             relationship.get(
#                 "target_concept",
#                 "",
#             )
#         )

#         if not source or not target:
#             return None

#         relationship_type = self._clean_string(
#             relationship.get(
#                 "relationship_type",
#                 "related_to",
#             )
#         )

#         if (
#             relationship_type
#             not in self.allowed_relationships
#         ):

#             relationship_type = (
#                 "related_to"
#             )

#         if (
#             self._is_numeric_only_concept(
#                 source
#             )
#             or self._is_numeric_only_concept(
#                 target
#             )
#         ):
#             return None

#         relationship[
#             "source_concept"
#         ] = source

#         relationship[
#             "target_concept"
#         ] = target

#         relationship[
#             "relationship_type"
#         ] = relationship_type

#         return relationship

#     # ==================================================================
#     # LLM EXTRACTION
#     # ==================================================================

#     async def _process_logical_unit(
#         self,
#         chunk_id: str,
#         chunk: Dict[str, Any],
#     ) -> Dict[str, List[Any]]:

#         start_time = time.perf_counter()

#         section_payload = (
#             self._format_logical_payload(
#                 chunk
#             )
#         )

#         elements = chunk.get(
#             "elements",
#             [],
#         )

#         chunk_pages = self._get_chunk_pages(
#             elements
#         )

#         if (
#             len(
#                 section_payload.strip()
#             )
#             < self.MIN_PAYLOAD_LENGTH
#         ):

#             return self._empty_extraction()

#         for attempt in range(
#             self.LLM_MAX_RETRIES + 1
#         ):

#             try:

#                 logger.debug(
#                     f"LLM extraction started: "
#                     f"{chunk_id}, "
#                     f"attempt={attempt + 1}"
#                 )

#                 completion = (
#                     await self.client.beta.chat.completions.parse(
#                         model=self.model_name,

#                         messages=[
#                             {
#                                 "role": "system",
#                                 "content": self._system_prompt,
#                             },
#                             {
#                                 "role": "user",
#                                 "content": (
#                                     "Extract the complete "
#                                     "TagTaste sensory knowledge "
#                                     "from this logical document "
#                                     "unit.\n\n"

#                                     "STRICT REQUIREMENTS:\n"
#                                     "1. Preserve product/sample context.\n"
#                                     "2. Preserve sensory attribute context.\n"
#                                     "3. Preserve descriptor context.\n"
#                                     "4. Preserve score and intensity context.\n"
#                                     "5. Preserve scale information.\n"
#                                     "6. Preserve table row/column semantics.\n"
#                                     "7. Do not create floating numbers.\n"
#                                     "8. Do not create floating descriptors.\n"
#                                     "9. Do not extract bibliographic citations as concepts.\n"
#                                     "10. Preserve hierarchy.\n"
#                                     "11. Use only explicitly supported relationships.\n"
#                                     "12. Preserve source page and element information when available.\n\n"
#                                     f"{section_payload}"
#                                 ),
#                             },
#                         ],

#                         response_format=KnowledgeExtractionPayload,

#                         temperature=0.0,
#                     )
#                 )

#                 message = (
#                     completion
#                     .choices[0]
#                     .message
#                 )

#                 result = message.parsed

#                 if not result:

#                     logger.warning(
#                         f"No structured result returned "
#                         f"for {chunk_id}"
#                     )

#                     return (
#                         self._empty_extraction()
#                     )

#                 extracted = (
#                     self._empty_extraction()
#                 )

#                 # ------------------------------------------------------
#                 # CONCEPTS
#                 # ------------------------------------------------------

#                 for concept in result.concepts:

#                     concept_dict = (
#                         concept.model_dump()
#                     )

#                     validated = (
#                         self._validate_concept(
#                             concept_dict,
#                             chunk_pages,
#                         )
#                     )

#                     if not validated:
#                         continue

#                     # Always attach chunk-level provenance.
#                     validated[
#                         "source_pages"
#                     ] = sorted(
#                         set(
#                             validated.get(
#                                 "source_pages",
#                                 [],
#                             )
#                             + chunk_pages
#                         ),
#                         key=lambda value: str(value),
#                     )

#                     validated[
#                         "source_page"
#                     ] = (
#                         validated[
#                             "source_pages"
#                         ][0]
#                         if validated[
#                             "source_pages"
#                         ]
#                         else None
#                     )

#                     validated[
#                         "chunk_id"
#                     ] = chunk_id

#                     extracted[
#                         "concepts"
#                     ].append(
#                         validated
#                     )

#                 # ------------------------------------------------------
#                 # RELATIONSHIPS
#                 # ------------------------------------------------------

#                 for relationship in (
#                     result.relationships
#                 ):

#                     relationship_dict = (
#                         relationship.model_dump()
#                     )

#                     validated_relationship = (
#                         self._validate_relationship(
#                             relationship_dict
#                         )
#                     )

#                     if validated_relationship:

#                         validated_relationship[
#                             "source_pages"
#                         ] = chunk_pages

#                         validated_relationship[
#                             "chunk_id"
#                         ] = chunk_id

#                         extracted[
#                             "relationships"
#                         ].append(
#                             validated_relationship
#                         )

#                 # ------------------------------------------------------
#                 # SCIENTIFIC RULES
#                 # ------------------------------------------------------

#                 extracted[
#                     "scientific_rules"
#                 ] = [
#                     rule.model_dump()
#                     for rule
#                     in result.scientific_rules
#                 ]

#                 # ------------------------------------------------------
#                 # PROCEDURES
#                 # ------------------------------------------------------

#                 extracted[
#                     "procedures"
#                 ] = [
#                     procedure.model_dump()
#                     for procedure
#                     in result.procedures
#                 ]

#                 elapsed = (
#                     time.perf_counter()
#                     - start_time
#                 )

#                 logger.debug(
#                     f"LLM extraction completed: "
#                     f"{chunk_id} in "
#                     f"{elapsed:.2f}s; "
#                     f"concepts="
#                     f"{len(extracted['concepts'])}, "
#                     f"relationships="
#                     f"{len(extracted['relationships'])}"
#                 )

#                 return extracted

#             except Exception as exc:

#                 error_text = str(exc)

#                 logger.warning(
#                     f"LLM extraction failed: "
#                     f"{chunk_id}, "
#                     f"attempt={attempt + 1}/"
#                     f"{self.LLM_MAX_RETRIES + 1}: "
#                     f"{error_text}"
#                 )

#                 if (
#                     attempt
#                     >= self.LLM_MAX_RETRIES
#                 ):

#                     logger.error(
#                         f"LLM extraction permanently "
#                         f"failed for {chunk_id}: "
#                         f"{error_text}",
#                         exc_info=True,
#                     )

#                     return (
#                         self._empty_extraction()
#                     )

#                 delay = (
#                     self.LLM_RETRY_BASE_DELAY
#                     * (2 ** attempt)
#                 )

#                 await asyncio.sleep(
#                     delay
#                 )

#         return self._empty_extraction()

#     # ==================================================================
#     # CONCEPT MERGE
#     # ==================================================================

#     def _merge_concept(
#         self,
#         existing: Dict[str, Any],
#         incoming: Dict[str, Any],
#     ) -> None:

#         # --------------------------------------------------------------
#         # Definition
#         # --------------------------------------------------------------

#         existing_definition = self._clean_string(
#             existing.get(
#                 "definition",
#                 "",
#             )
#         )

#         incoming_definition = self._clean_string(
#             incoming.get(
#                 "definition",
#                 "",
#             )
#         )

#         if (
#             not existing_definition
#             and incoming_definition
#         ):

#             existing[
#                 "definition"
#             ] = incoming_definition

#         # --------------------------------------------------------------
#         # Synonyms
#         # --------------------------------------------------------------

#         existing_synonyms = set(
#             existing.get(
#                 "synonyms",
#                 [],
#             )
#         )

#         incoming_synonyms = set(
#             incoming.get(
#                 "synonyms",
#                 [],
#             )
#         )

#         existing[
#             "synonyms"
#         ] = sorted(
#             existing_synonyms
#             | incoming_synonyms
#         )

#         # --------------------------------------------------------------
#         # Keywords
#         # --------------------------------------------------------------

#         existing_keywords = set(
#             existing.get(
#                 "keywords",
#                 [],
#             )
#         )

#         incoming_keywords = set(
#             incoming.get(
#                 "keywords",
#                 [],
#             )
#         )

#         existing[
#             "keywords"
#         ] = sorted(
#             existing_keywords
#             | incoming_keywords
#         )[:20]

#         # --------------------------------------------------------------
#         # Hierarchy
#         # --------------------------------------------------------------

#         existing_hierarchy = self._clean_string(
#             existing.get(
#                 "hierarchy_context",
#                 "",
#             )
#         )

#         incoming_hierarchy = self._clean_string(
#             incoming.get(
#                 "hierarchy_context",
#                 "",
#             )
#         )

#         hierarchy_parts = []

#         for value in (
#             existing_hierarchy,
#             incoming_hierarchy,
#         ):

#             if not value:
#                 continue

#             for part in value.split("|"):

#                 part = self._clean_string(
#                     part
#                 )

#                 if (
#                     part
#                     and part
#                     not in hierarchy_parts
#                 ):

#                     hierarchy_parts.append(
#                         part
#                     )

#         existing[
#             "hierarchy_context"
#         ] = " | ".join(
#             hierarchy_parts
#         )

#         # --------------------------------------------------------------
#         # Source pages
#         # --------------------------------------------------------------

#         pages = []

#         for page in (
#             existing.get(
#                 "source_pages",
#                 [],
#             )
#             + incoming.get(
#                 "source_pages",
#                 [],
#             )
#         ):

#             if (
#                 page is not None
#                 and page not in pages
#             ):

#                 pages.append(page)

#         pages.sort(
#             key=lambda value: str(value)
#         )

#         existing[
#             "source_pages"
#         ] = pages

#         existing[
#             "source_page"
#         ] = (
#             pages[0]
#             if pages
#             else None
#         )

#         # --------------------------------------------------------------
#         # Element IDs
#         # --------------------------------------------------------------

#         element_ids = set(
#             existing.get(
#                 "element_ids",
#                 [],
#             )
#         )

#         element_ids.update(
#             incoming.get(
#                 "element_ids",
#                 [],
#             )
#         )

#         existing[
#             "element_ids"
#         ] = sorted(
#             element_ids
#         )

#     # ==================================================================
#     # GLOBAL GRAPH STITCHING
#     # ==================================================================

#     def _stitch_global_graph(
#         self,
#         raw_concepts: List[Dict[str, Any]],
#         raw_relationships: List[Dict[str, Any]],
#     ) -> Tuple[
#         List[Dict[str, Any]],
#         List[Dict[str, Any]],
#     ]:

#         merged_concepts: Dict[
#             str,
#             Dict[str, Any],
#         ] = {}

#         # --------------------------------------------------------------
#         # PASS 1: Concept validation + deduplication
#         # --------------------------------------------------------------

#         for raw_concept in raw_concepts:

#             if not isinstance(
#                 raw_concept,
#                 dict,
#             ):
#                 continue

#             concept = self._validate_concept(
#                 raw_concept,
#                 raw_concept.get(
#                     "source_pages",
#                     [],
#                 ),
#             )

#             if not concept:
#                 continue

#             concept_name = concept[
#                 "canonical_name"
#             ]

#             key = self._normalize_key(
#                 concept_name
#             )

#             if key == "unknown":
#                 continue

#             # ----------------------------------------------------------
#             # Important:
#             #
#             # Do not merge concepts solely because they share a loose
#             # substring. We use normalized exact names.
#             # ----------------------------------------------------------

#             if key not in merged_concepts:

#                 merged_concepts[
#                     key
#                 ] = concept

#             else:

#                 self._merge_concept(
#                     merged_concepts[key],
#                     concept,
#                 )

#         # --------------------------------------------------------------
#         # PASS 2: Relationship validation
#         # --------------------------------------------------------------

#         valid_keys = set(
#             merged_concepts.keys()
#         )

#         clean_relationships = []

#         seen_relationships = set()

#         for raw_relationship in (
#             raw_relationships
#         ):

#             relationship = (
#                 self._validate_relationship(
#                     raw_relationship
#                 )
#             )

#             if not relationship:
#                 continue

#             source_name = relationship[
#                 "source_concept"
#             ]

#             target_name = relationship[
#                 "target_concept"
#             ]

#             source_key = self._normalize_key(
#                 source_name
#             )

#             target_key = self._normalize_key(
#                 target_name
#             )

#             # Both nodes must survive.
#             if (
#                 source_key not in valid_keys
#                 or target_key not in valid_keys
#             ):
#                 continue

#             # No self loops.
#             if source_key == target_key:
#                 continue

#             relationship[
#                 "source_concept"
#             ] = merged_concepts[
#                 source_key
#             ][
#                 "canonical_name"
#             ]

#             relationship[
#                 "target_concept"
#             ] = merged_concepts[
#                 target_key
#             ][
#                 "canonical_name"
#             ]

#             relationship_type = (
#                 relationship[
#                     "relationship_type"
#                 ]
#             )

#             signature = (
#                 f"{source_key}:::"
#                 f"{relationship_type}:::"
#                 f"{target_key}"
#             )

#             if signature in seen_relationships:
#                 continue

#             seen_relationships.add(
#                 signature
#             )

#             # ----------------------------------------------------------
#             # Merge relationship provenance.
#             # ----------------------------------------------------------

#             relationship_pages = relationship.get(
#                 "source_pages",
#                 [],
#             )

#             if not isinstance(
#                 relationship_pages,
#                 list,
#             ):

#                 relationship_pages = [
#                     relationship_pages
#                 ]

#             relationship[
#                 "source_pages"
#             ] = sorted(
#                 {
#                     page
#                     for page in relationship_pages
#                     if page is not None
#                 },
#                 key=lambda value: str(value),
#             )

#             clean_relationships.append(
#                 relationship
#             )

#         return (
#             list(
#                 merged_concepts.values()
#             ),
#             clean_relationships,
#         )

#     # ==================================================================
#     # DEDUPLICATE GENERIC OBJECTS
#     # ==================================================================

#     def _deduplicate_objects(
#         self,
#         objects: List[Dict[str, Any]],
#     ) -> List[Dict[str, Any]]:

#         result = []

#         seen = set()

#         for item in objects:

#             if not isinstance(
#                 item,
#                 dict,
#             ):
#                 continue

#             normalized = json.dumps(
#                 item,
#                 sort_keys=True,
#                 ensure_ascii=False,
#                 default=str,
#             )

#             signature = re.sub(
#                 r"\s+",
#                 " ",
#                 normalized,
#             )

#             if signature in seen:
#                 continue

#             seen.add(signature)

#             result.append(
#                 item
#             )

#         return result

#     # ==================================================================
#     # METADATA READ
#     # ==================================================================

#     def _read_metadata(
#         self,
#         metadata_path: Path,
#     ) -> Dict[str, Any]:

#         if not metadata_path.exists():
#             return {}

#         try:

#             with open(
#                 metadata_path,
#                 "r",
#                 encoding="utf-8",
#             ) as file:

#                 value = json.load(file)

#                 if isinstance(
#                     value,
#                     dict,
#                 ):
#                     return value

#         except Exception as exc:

#             logger.warning(
#                 f"Could not read metadata "
#                 f"{metadata_path}: {exc}"
#             )

#         return {}

#     # ==================================================================
#     # ATOMIC JSON WRITE
#     # ==================================================================

#     def _atomic_write_json(
#         self,
#         path: Path,
#         data: Dict[str, Any],
#     ) -> None:

#         path.parent.mkdir(
#             parents=True,
#             exist_ok=True,
#         )

#         temporary_path = path.with_suffix(
#             path.suffix + ".tmp"
#         )

#         with open(
#             temporary_path,
#             "w",
#             encoding="utf-8",
#         ) as file:

#             json.dump(
#                 data,
#                 file,
#                 indent=4,
#                 ensure_ascii=False,
#                 default=str,
#             )

#             file.flush()

#         temporary_path.replace(
#             path
#         )

#     # ==================================================================
#     # UPDATE PIPELINE METADATA
#     # ==================================================================

#     def _update_metadata_status(
#         self,
#         metadata_path: Path,
#         document_id: str,
#         status: str,
#     ) -> None:

#         if not metadata_path.exists():
#             return

#         metadata = self._read_metadata(
#             metadata_path
#         )

#         if not metadata:
#             return

#         metadata[
#             "pipeline_status"
#         ] = status

#         if status == "KNOWLEDGE_EXTRACTED":

#             metadata[
#                 "next_step"
#             ] = (
#                 f"{settings.API_V1_STR}"
#                 f"/documents/{document_id}"
#                 f"/knowledge"
#             )

#         elif status == "KNOWLEDGE_EXTRACTION_FAILED":

#             metadata[
#                 "next_step"
#             ] = None

#         try:

#             self._atomic_write_json(
#                 metadata_path,
#                 metadata,
#             )

#         except Exception as exc:

#             logger.warning(
#                 f"Could not update metadata "
#                 f"for {document_id}: {exc}"
#             )

#     # ==================================================================
#     # MASTER PIPELINE
#     # ==================================================================

#     async def extract_knowledge(
#         self,
#         document_id: str,
#     ) -> Dict[str, Any]:

#         started_at = (
#             time.perf_counter()
#         )

#         processed_base = (
#             self.processed_dir
#             / document_id
#         )

#         normalized_path = (
#             processed_base
#             / "normalized_elements.jsonl"
#         )

#         metadata_path = (
#             self.raw_dir
#             / document_id
#             / "metadata.json"
#         )

#         extracted_knowledge_path = (
#             processed_base
#             / "extracted_knowledge.json"
#         )

#         logger.info(
#             f"Starting TagTaste sensory "
#             f"knowledge extraction "
#             f"for {document_id}"
#         )

#         try:

#             # ==========================================================
#             # 1. WAIT FOR STRUCTURAL EXTRACTION
#             # ==========================================================

#             await self._wait_for_normalized_file(
#                 normalized_path,
#                 document_id,
#             )

#             # ==========================================================
#             # 2. DOCUMENT METADATA
#             # ==========================================================

#             metadata = self._read_metadata(
#                 metadata_path
#             )

#             book_title = metadata.get(
#                 "title",
#                 "Scientific Document",
#             )

#             # ==========================================================
#             # 3. LOAD NORMALIZED ELEMENTS
#             # ==========================================================

#             elements = (
#                 self._load_normalized_elements(
#                     normalized_path
#                 )
#             )

#             if not elements:

#                 logger.warning(
#                     f"No normalized elements found "
#                     f"for {document_id}"
#                 )

#                 empty_artifact = {
#                     "document_id": document_id,
#                     "concepts": [],
#                     "relationships": [],
#                     "scientific_rules": [],
#                     "procedures": [],
#                 }

#                 self._atomic_write_json(
#                     extracted_knowledge_path,
#                     empty_artifact,
#                 )

#                 self._update_metadata_status(
#                     metadata_path,
#                     document_id,
#                     "KNOWLEDGE_EXTRACTED",
#                 )

#                 return {
#                     "document_id": document_id,
#                     "pipeline_status": (
#                         "KNOWLEDGE_EXTRACTED"
#                     ),
#                     "extracted_stats": {
#                         "raw_concepts_found": 0,
#                         "clean_concepts_saved": 0,
#                         "relationships_extracted": 0,
#                     },
#                     "knowledge_artifact_path": str(
#                         extracted_knowledge_path.relative_to(
#                             settings.BASE_DIR
#                         )
#                     ),
#                 }

#             logger.info(
#                 f"Loaded {len(elements)} "
#                 f"normalized elements "
#                 f"for {document_id}"
#             )

#             # ==========================================================
#             # 4. PRE-CACHE
#             # ==========================================================

#             cache_start = (
#                 time.perf_counter()
#             )

#             self._prepare_element_cache(
#                 elements
#             )

#             logger.info(
#                 f"Element cache prepared for "
#                 f"{document_id} in "
#                 f"{time.perf_counter() - cache_start:.2f}s"
#             )

#             # ==========================================================
#             # 5. BUILD LOGICAL UNITS
#             # ==========================================================

#             split_start = (
#                 time.perf_counter()
#             )

#             logical_units = (
#                 self._hierarchical_split(
#                     elements,
#                     book_title,
#                     depth=0,
#                 )
#             )

#             split_elapsed = (
#                 time.perf_counter()
#                 - split_start
#             )

#             total_units = len(
#                 logical_units
#             )

#             logger.info(
#                 f"Created {total_units} "
#                 f"logical sensory units "
#                 f"for {document_id} "
#                 f"in {split_elapsed:.2f}s. "
#                 f"Concurrency="
#                 f"{self.max_concurrent_requests}"
#             )

#             # ==========================================================
#             # 6. CONCURRENT LLM EXTRACTION
#             # ==========================================================

#             semaphore = asyncio.Semaphore(
#                 self.max_concurrent_requests
#             )

#             async def bounded_process(
#                 unit_index: int,
#                 unit_data: Dict[str, Any],
#             ):

#                 async with semaphore:

#                     try:

#                         return await (
#                             self._process_logical_unit(
#                                 f"unit_{unit_index}",
#                                 unit_data,
#                             )
#                         )

#                     except Exception as exc:

#                         logger.error(
#                             f"Unexpected extraction "
#                             f"failure in unit "
#                             f"{unit_index}: "
#                             f"{exc}",
#                             exc_info=True,
#                         )

#                         return (
#                             self._empty_extraction()
#                         )

#             tasks = [
#                 asyncio.create_task(
#                     bounded_process(
#                         index,
#                         unit,
#                     )
#                 )
#                 for index, unit
#                 in enumerate(
#                     logical_units
#                 )
#             ]

#             raw_concepts = []
#             raw_relationships = []
#             scientific_rules = []
#             procedures = []

#             completed = 0
#             successful_units = 0
#             failed_units = 0

#             llm_start = (
#                 time.perf_counter()
#             )

#             for completed_task in (
#                 asyncio.as_completed(
#                     tasks
#                 )
#             ):

#                 try:

#                     result = await (
#                         completed_task
#                     )

#                     if (
#                         result.get(
#                             "concepts"
#                         )
#                         or result.get(
#                             "relationships"
#                         )
#                         or result.get(
#                             "scientific_rules"
#                         )
#                         or result.get(
#                             "procedures"
#                         )
#                     ):

#                         successful_units += 1

#                     else:

#                         failed_units += 1

#                 except Exception as exc:

#                     failed_units += 1

#                     logger.error(
#                         f"Logical unit failed "
#                         f"for {document_id}: "
#                         f"{exc}",
#                         exc_info=True,
#                     )

#                     result = (
#                         self._empty_extraction()
#                     )

#                 completed += 1

#                 raw_concepts.extend(
#                     result.get(
#                         "concepts",
#                         [],
#                     )
#                 )

#                 raw_relationships.extend(
#                     result.get(
#                         "relationships",
#                         [],
#                     )
#                 )

#                 scientific_rules.extend(
#                     result.get(
#                         "scientific_rules",
#                         [],
#                     )
#                 )

#                 procedures.extend(
#                     result.get(
#                         "procedures",
#                         [],
#                     )
#                 )

#                 logger.debug(
#                     f"Knowledge extraction "
#                     f"progress for "
#                     f"{document_id}: "
#                     f"{completed}/"
#                     f"{total_units}"
#                 )

#             llm_elapsed = (
#                 time.perf_counter()
#                 - llm_start
#             )

#             logger.info(
#                 f"LLM sensory extraction "
#                 f"completed for "
#                 f"{document_id} in "
#                 f"{llm_elapsed:.2f}s; "
#                 f"successful_units="
#                 f"{successful_units}; "
#                 f"failed_units="
#                 f"{failed_units}"
#             )

#             # ==========================================================
#             # IMPORTANT:
#             #
#             # If every logical unit failed, do not falsely report a
#             # successful extraction.
#             # ==========================================================

#             if (
#                 total_units > 0
#                 and successful_units == 0
#             ):

#                 raise ProcessingError(
#                     f"All {total_units} knowledge "
#                     f"extraction units failed for "
#                     f"{document_id}."
#                 )

#             # ==========================================================
#             # 7. GLOBAL GRAPH STITCHING
#             # ==========================================================

#             stitch_start = (
#                 time.perf_counter()
#             )

#             (
#                 clean_concepts,
#                 clean_relationships,
#             ) = self._stitch_global_graph(
#                 raw_concepts,
#                 raw_relationships,
#             )

#             stitch_elapsed = (
#                 time.perf_counter()
#                 - stitch_start
#             )

#             logger.info(
#                 f"Global sensory graph "
#                 f"stitching completed for "
#                 f"{document_id} in "
#                 f"{stitch_elapsed:.2f}s"
#             )

#             # ==========================================================
#             # 8. DEDUPLICATE RULES / PROCEDURES
#             # ==========================================================

#             scientific_rules = (
#                 self._deduplicate_objects(
#                     scientific_rules
#                 )
#             )

#             procedures = (
#                 self._deduplicate_objects(
#                     procedures
#                 )
#             )

#             # ==========================================================
#             # 9. BUILD FINAL ARTIFACT
#             # ==========================================================

#             master_knowledge = {
#                 "document_id": document_id,

#                 "concepts": clean_concepts,

#                 "relationships": clean_relationships,

#                 "scientific_rules": (
#                     scientific_rules
#                 ),

#                 "procedures": procedures,
#             }

#             # ==========================================================
#             # 10. ATOMIC SAVE
#             # ==========================================================

#             self._atomic_write_json(
#                 extracted_knowledge_path,
#                 master_knowledge,
#             )

#             # ==========================================================
#             # 11. UPDATE PIPELINE STATUS
#             # ==========================================================

#             self._update_metadata_status(
#                 metadata_path,
#                 document_id,
#                 "KNOWLEDGE_EXTRACTED",
#             )

#             # ==========================================================
#             # 12. FINAL RESPONSE
#             # ==========================================================

#             total_elapsed = (
#                 time.perf_counter()
#                 - started_at
#             )

#             logger.info(
#                 f"TagTaste sensory knowledge "
#                 f"extraction completed for "
#                 f"{document_id} in "
#                 f"{total_elapsed:.2f}s. "
#                 f"Raw concepts="
#                 f"{len(raw_concepts)}, "
#                 f"Clean concepts="
#                 f"{len(clean_concepts)}, "
#                 f"Relationships="
#                 f"{len(clean_relationships)}"
#             )

#             # Keep existing API response shape.
#             return {
#                 "document_id": document_id,
#                 "pipeline_status": (
#                     "KNOWLEDGE_EXTRACTED"
#                 ),
#                 "extracted_stats": {
#                     "raw_concepts_found": len(
#                         raw_concepts
#                     ),
#                     "clean_concepts_saved": len(
#                         clean_concepts
#                     ),
#                     "relationships_extracted": len(
#                         clean_relationships
#                     ),
#                 },
#                 "knowledge_artifact_path": str(
#                     extracted_knowledge_path.relative_to(
#                         settings.BASE_DIR
#                     )
#                 ),
#             }

#         except (
#             DocumentNotFoundError,
#             ProcessingError,
#         ):

#             logger.error(
#                 f"Knowledge extraction could not "
#                 f"complete for {document_id}",
#                 exc_info=True,
#             )

#             self._update_metadata_status(
#                 metadata_path,
#                 document_id,
#                 "KNOWLEDGE_EXTRACTION_FAILED",
#             )

#             # Never allow background-task exceptions to escape.
#             return {
#                 "document_id": document_id,
#                 "pipeline_status": (
#                     "KNOWLEDGE_EXTRACTION_FAILED"
#                 ),
#                 "extracted_stats": {
#                     "raw_concepts_found": 0,
#                     "clean_concepts_saved": 0,
#                     "relationships_extracted": 0,
#                 },
#                 "knowledge_artifact_path": None,
#             }

#         except (
#             StorageError,
#         ) as exc:

#             logger.error(
#                 f"Storage failure during knowledge "
#                 f"extraction for {document_id}: "
#                 f"{exc}",
#                 exc_info=True,
#             )

#             self._update_metadata_status(
#                 metadata_path,
#                 document_id,
#                 "KNOWLEDGE_EXTRACTION_FAILED",
#             )

#             return {
#                 "document_id": document_id,
#                 "pipeline_status": (
#                     "KNOWLEDGE_EXTRACTION_FAILED"
#                 ),
#                 "extracted_stats": {
#                     "raw_concepts_found": 0,
#                     "clean_concepts_saved": 0,
#                     "relationships_extracted": 0,
#                 },
#                 "knowledge_artifact_path": None,
#             }

#         except Exception as exc:

#             logger.error(
#                 f"Knowledge extraction failed "
#                 f"for {document_id}: "
#                 f"{exc}",
#                 exc_info=True,
#             )

#             self._update_metadata_status(
#                 metadata_path,
#                 document_id,
#                 "KNOWLEDGE_EXTRACTION_FAILED",
#             )

#             # Background task must not raise after 202.
#             return {
#                 "document_id": document_id,
#                 "pipeline_status": (
#                     "KNOWLEDGE_EXTRACTION_FAILED"
#                 ),
#                 "extracted_stats": {
#                     "raw_concepts_found": 0,
#                     "clean_concepts_saved": 0,
#                     "relationships_extracted": 0,
#                 },
#                 "knowledge_artifact_path": None,
#             }

















# app/services/knowledge_service.py

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from openai import AsyncOpenAI

try:
    import tiktoken

    _TOKENIZER = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        if not text:
            return 0
        return len(_TOKENIZER.encode(text))

except ImportError:

    def count_tokens(text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // 4)


from app.core.config import settings
from app.core.exceptions import (
    DocumentNotFoundError,
    ProcessingError,
    StorageError,
)
from app.core.logger import logger
from app.models.knowledge import KnowledgeExtractionPayload


class KnowledgeService:
    """
    Fast TagTaste sensory knowledge extraction service.

    Pipeline:

        normalized_elements.jsonl
                    |
                    v
             smart chunking
                    |
                    v
          concurrent LLM extraction
                    |
                    v
          deterministic stitching
                    |
                    v
       extracted_knowledge.json

    Performance strategy:

    1. Larger but semantically safe chunks.
    2. 15-20 concurrent LLM requests.
    3. Compact system prompt.
    4. No unnecessary prompt duplication.
    5. Shorter request timeout.
    6. Limited retry only for transient failures.
    7. Preserve table semantics.
    8. Preserve hierarchy.
    9. Preserve sensory relationships.
    10. Deterministic global deduplication.
    """

    # ==================================================================
    # PERFORMANCE CONFIGURATION
    # ==================================================================

    DEFAULT_MODEL = "gpt-4o-mini"

    # Increase this from 10.
    DEFAULT_MAX_CONCURRENT_REQUESTS = 16

    # Previously 6000.
    # 3500-4500 is generally sufficient for structured extraction.
    MAX_TOKENS_PER_CHUNK = 4500

    # Only carry a small amount of context.
    OVERLAP_ELEMENTS = 2

    MIN_PAYLOAD_LENGTH = 80

    # ------------------------------------------------------------------
    # STRUCTURAL FILE
    # ------------------------------------------------------------------

    NORMALIZED_FILE_WAIT_SECONDS = 90.0
    NORMALIZED_FILE_POLL_INTERVAL = 0.25
    NORMALIZED_FILE_STABLE_CHECKS = 2

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------

    # Keep retries low because retries directly affect latency.
    LLM_MAX_RETRIES = 1

    LLM_RETRY_BASE_DELAY = 0.4

    # Client timeout.
    DEFAULT_OPENAI_TIMEOUT = 90.0

    # ------------------------------------------------------------------
    # METADATA
    # ------------------------------------------------------------------

    METADATA_KEYWORDS = {
        "press",
        "isbn",
        "copyright",
        "edition",
        "publisher",
        "author",
        "bibliography",
        "reference",
        "printing",
    }

    # ==================================================================
    # INITIALIZATION
    # ==================================================================

    def __init__(self):

        self.raw_dir = Path(
            settings.STORAGE_RAW_DIR
        )

        self.processed_dir = Path(
            settings.STORAGE_PROCESSED_DIR
        )

        # --------------------------------------------------------------
        # OPENAI CLIENT
        # --------------------------------------------------------------

        configured_timeout = getattr(
            settings,
            "OPENAI_TIMEOUT",
            self.DEFAULT_OPENAI_TIMEOUT,
        )

        try:
            configured_timeout = float(
                configured_timeout
            )
        except (
            TypeError,
            ValueError,
        ):
            configured_timeout = (
                self.DEFAULT_OPENAI_TIMEOUT
            )

        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=configured_timeout,
            max_retries=0,
        )

        # --------------------------------------------------------------
        # MODEL
        # --------------------------------------------------------------

        self.model_name = getattr(
            settings,
            "OPENAI_KNOWLEDGE_MODEL",
            self.DEFAULT_MODEL,
        )

        # --------------------------------------------------------------
        # CONCURRENCY
        # --------------------------------------------------------------

        configured_concurrency = getattr(
            settings,
            "MAX_CONCURRENT_EXTRACTIONS",
            self.DEFAULT_MAX_CONCURRENT_REQUESTS,
        )

        try:
            configured_concurrency = int(
                configured_concurrency
            )
        except (
            TypeError,
            ValueError,
        ):
            configured_concurrency = (
                self.DEFAULT_MAX_CONCURRENT_REQUESTS
            )

        self.max_concurrent_requests = max(
            1,
            configured_concurrency,
        )

        # --------------------------------------------------------------
        # CHUNKING
        # --------------------------------------------------------------

        self.max_tokens_per_chunk = (
            self.MAX_TOKENS_PER_CHUNK
        )

        self.overlap_elements = (
            self.OVERLAP_ELEMENTS
        )

        # --------------------------------------------------------------
        # ONTOLOGY
        # --------------------------------------------------------------

        self.ontology_categories = [
            "Entity",
            "Method",
            "Theory",
            "Process",
            "Material",
            "Chemical",
            "Instrument",
            "Organization",
            "Measurement",
            "Property",
            "Sensory_Attribute",
        ]

        # --------------------------------------------------------------
        # RELATIONSHIPS
        # --------------------------------------------------------------

        self.sensory_relationships = [
            "has_sensory_attribute",
            "has_descriptor",
            "has_intensity",
            "has_score",
            "uses_scale",
            "measured_by",
            "evaluated_by",
            "compared_with",
            "benchmarked_against",
            "prepared_by",
            "contains",
            "derived_from",
            "belongs_to",
            "part_of",
            "associated_with",
            "caused_by",
            "influences",
            "correlates_with",
            "defined_by",
            "measured_under",
            "tested_by",
            "has_method",
            "has_property",
            "related_to",
        ]

        self.allowed_relationships = set(
            self.sensory_relationships
        )

        # --------------------------------------------------------------
        # CACHE
        # --------------------------------------------------------------

        self._element_text_cache: Dict[int, str] = {}
        self._element_token_cache: Dict[int, int] = {}

        # --------------------------------------------------------------
        # PROMPT
        # --------------------------------------------------------------

        self._system_prompt = (
            self._build_system_prompt()
        )

    # ==================================================================
    # EMPTY RESULT
    # ==================================================================

    @staticmethod
    def _empty_extraction() -> Dict[str, List[Any]]:

        return {
            "concepts": [],
            "relationships": [],
            "scientific_rules": [],
            "procedures": [],
        }

    # ==================================================================
    # SYSTEM PROMPT
    # ==================================================================

    def _build_system_prompt(self) -> str:

        ontology = ", ".join(
            self.ontology_categories
        )

        relationships = ", ".join(
            self.sensory_relationships
        )

        return f"""
You are the TagTaste sensory knowledge graph extraction engine.

Extract ONLY knowledge explicitly supported by the supplied document.

Ontology categories:
{ontology}

Allowed relationships:
{relationships}

PRIMARY GOAL
-----------
Build a semantic sensory knowledge graph.

Preserve relationships between:

product/sample
sensory attribute
descriptor
score
intensity
scale
benchmark/reference
method
preparation
measurement
instrument
material
chemical
procedure
scientific rule

SENSORY CONTEXT
---------------
Recognize explicit attributes such as:

appearance, aroma, odor, flavor, taste, mouthfeel, texture,
aftertaste, finish, liking, acceptability, sweetness,
sourness, bitterness, saltiness, umami, astringency,
acidity, spiciness, heat, freshness, color, opacity,
clarity, viscosity, creaminess, crispness, crunchiness,
hardness, softness, chewiness, juiciness, tenderness,
thickness, coating, persistence, balance and other
attributes explicitly present in the document.

NUMERIC VALUES
--------------
Never create floating numeric concepts.

Example:

"Sweetness = 7/9"

means the value 7 belongs to Sweetness and the scale is 9-point.

"pH = 4.2"

means 4.2 belongs to pH.

Keep scores, measurements, concentrations, percentages,
temperature, pH, viscosity, time and other values attached
to their explicit parent concept.

TABLES
------
Tables contain semantic relationships.

Example:

Sample | Sweetness | Bitterness
A      | 7         | 2

means:

A -> Sweetness -> score 7
A -> Bitterness -> score 2

Do NOT extract 7 and 2 as independent concepts.

DESCRIPTORS
-----------
A descriptor must remain connected to its product/sample
or sensory attribute context.

Example:

Descriptor | Intensity
Vanilla    | Strong

means Vanilla has_intensity Strong.

SAMPLES
-------
Preserve distinctions between:

sample
product
formulation
treatment
batch
benchmark
reference
control

Do not merge samples merely because names look similar.

RELATIONSHIPS
-------------
Only create relationships explicitly supported by the input.

Never infer a scientifically plausible relationship unless
the document states or clearly expresses it.

HIERARCHY
---------
Preserve the supplied hierarchy.

Populate hierarchy_context using the hierarchy markers.

METADATA
--------
Ignore bibliographic metadata such as author, publisher,
ISBN, copyright and edition unless it is explicitly domain
knowledge.

IMPORTANT
---------
Do not invent:

- sensory attributes
- measurements
- scores
- scales
- benchmarks
- ingredients
- scientific relationships
- causes
- meanings

Return ONLY the structured KnowledgeExtractionPayload.
"""

    # ==================================================================
    # TABLE RENDERING
    # ==================================================================

    def _render_table_markdown(
        self,
        cells: List[Dict],
    ) -> str:

        if not cells:
            return ""

        max_row = max(
            (
                int(
                    cell.get(
                        "row_idx",
                        0,
                    )
                )
                for cell in cells
            ),
            default=-1,
        )

        max_col = max(
            (
                int(
                    cell.get(
                        "col_idx",
                        0,
                    )
                )
                for cell in cells
            ),
            default=-1,
        )

        if max_row < 0 or max_col < 0:
            return ""

        grid = [
            ["" for _ in range(max_col + 1)]
            for _ in range(max_row + 1)
        ]

        for cell in cells:

            row_idx = int(
                cell.get(
                    "row_idx",
                    0,
                )
            )

            col_idx = int(
                cell.get(
                    "col_idx",
                    0,
                )
            )

            if (
                row_idx < 0
                or col_idx < 0
                or row_idx > max_row
                or col_idx > max_col
            ):
                continue

            value = str(
                cell.get(
                    "text",
                    "",
                )
                or ""
            )

            value = (
                value
                .replace("\n", " ")
                .replace("|", "/")
                .strip()
            )

            grid[row_idx][col_idx] = value

        if not grid:
            return ""

        lines = []

        # --------------------------------------------------------------
        # Header
        # --------------------------------------------------------------

        header = grid[0]

        lines.append(
            "| "
            + " | ".join(header)
            + " |"
        )

        lines.append(
            "| "
            + " | ".join(
                "---"
                for _ in header
            )
            + " |"
        )

        # --------------------------------------------------------------
        # Rows
        # --------------------------------------------------------------

        for row in grid[1:]:

            lines.append(
                "| "
                + " | ".join(row)
                + " |"
            )

        return "\n".join(lines)

    # ==================================================================
    # ELEMENT TEXT
    # ==================================================================

    def _get_element_text(
        self,
        element: Dict,
    ) -> str:

        cache_key = id(element)

        cached = self._element_text_cache.get(
            cache_key
        )

        if cached is not None:
            return cached

        if element.get("type") == "table":

            text = self._render_table_markdown(
                element.get(
                    "cells",
                    [],
                )
            )

        else:

            text = str(
                element.get(
                    "text",
                    "",
                )
                or ""
            )

        self._element_text_cache[
            cache_key
        ] = text

        return text

    # ==================================================================
    # TOKEN COUNT
    # ==================================================================

    def _get_element_tokens(
        self,
        element: Dict,
    ) -> int:

        cache_key = id(element)

        cached = self._element_token_cache.get(
            cache_key
        )

        if cached is not None:
            return cached

        tokens = count_tokens(
            self._get_element_text(
                element
            )
        )

        self._element_token_cache[
            cache_key
        ] = tokens

        return tokens

    # ==================================================================
    # WAIT FOR NORMALIZED FILE
    # ==================================================================

    async def _wait_for_normalized_file(
        self,
        normalized_path: Path,
        document_id: str,
    ) -> None:

        deadline = (
            time.monotonic()
            + self.NORMALIZED_FILE_WAIT_SECONDS
        )

        last_signature = None
        stable_count = 0

        while time.monotonic() < deadline:

            if normalized_path.exists():

                try:

                    stat = normalized_path.stat()

                    if stat.st_size > 0:

                        valid_lines = 0
                        invalid_lines = 0

                        with open(
                            normalized_path,
                            "r",
                            encoding="utf-8",
                        ) as file:

                            for line in file:

                                line = line.strip()

                                if not line:
                                    continue

                                try:
                                    json.loads(line)
                                    valid_lines += 1

                                except json.JSONDecodeError:
                                    invalid_lines += 1

                                    # File is probably still being
                                    # written.
                                    break

                        signature = (
                            stat.st_size,
                            stat.st_mtime_ns,
                            valid_lines,
                        )

                        if (
                            valid_lines > 0
                            and invalid_lines == 0
                        ):

                            if (
                                signature
                                == last_signature
                            ):
                                stable_count += 1
                            else:
                                stable_count = 1

                            last_signature = signature

                            if (
                                stable_count
                                >= self.NORMALIZED_FILE_STABLE_CHECKS
                            ):

                                logger.info(
                                    f"Normalized elements ready "
                                    f"for {document_id}: "
                                    f"{valid_lines} records."
                                )

                                return

                        else:
                            stable_count = 0

                except (
                    OSError,
                    PermissionError,
                ) as exc:

                    logger.debug(
                        f"Normalized file not ready: "
                        f"{exc}"
                    )

            await asyncio.sleep(
                self.NORMALIZED_FILE_POLL_INTERVAL
            )

        raise ProcessingError(
            f"Normalized elements are not ready for "
            f"{document_id} after "
            f"{self.NORMALIZED_FILE_WAIT_SECONDS:.0f}s. "
            f"Expected file: {normalized_path}"
        )

    # ==================================================================
    # LOAD NORMALIZED JSONL
    # ==================================================================

    def _load_normalized_elements(
        self,
        normalized_path: Path,
    ) -> List[Dict]:

        elements = []

        with open(
            normalized_path,
            "r",
            encoding="utf-8",
        ) as file:

            for line_number, line in enumerate(
                file,
                start=1,
            ):

                line = line.strip()

                if not line:
                    continue

                try:

                    value = json.loads(line)

                    if isinstance(
                        value,
                        dict,
                    ):
                        elements.append(value)

                except json.JSONDecodeError as exc:

                    logger.warning(
                        f"Skipping invalid JSONL line "
                        f"{line_number}: {exc}"
                    )

        return elements

    # ==================================================================
    # CACHE
    # ==================================================================

    def _prepare_element_cache(
        self,
        elements: List[Dict],
    ) -> None:

        self._element_text_cache.clear()
        self._element_token_cache.clear()

        for element in elements:

            key = id(element)

            text = self._get_element_text(
                element
            )

            self._element_text_cache[key] = text

            self._element_token_cache[key] = (
                count_tokens(text)
            )

    # ==================================================================
    # HIERARCHY-AWARE CHUNKING
    # ==================================================================

    def _hierarchical_split(
        self,
        elements: List[Dict],
        book_title: str,
        depth: int = 0,
    ) -> List[Dict]:

        if not elements:
            return []

        total_tokens = sum(
            self._get_element_tokens(e)
            for e in elements
        )

        # --------------------------------------------------------------
        # This is the key performance change.
        # Keep sections together until 4500 tokens.
        # --------------------------------------------------------------

        if total_tokens <= self.max_tokens_per_chunk:

            return [
                {
                    "book_title": book_title,
                    "elements": elements,
                }
            ]

        groups = []
        current_group = []
        current_key = None

        for element in elements:

            path_nodes = (
                element
                .get(
                    "context",
                    {},
                )
                .get(
                    "path",
                    [],
                )
            )

            path_texts = [
                str(
                    node.get(
                        "text",
                        "",
                    )
                )
                for node in path_nodes
            ]

            key = (
                path_texts[depth]
                if depth < len(path_texts)
                else ""
            )

            if (
                current_group
                and key != current_key
            ):

                groups.append(
                    current_group
                )

                current_group = []

            current_key = key

            current_group.append(
                element
            )

        if current_group:
            groups.append(
                current_group
            )

        if len(groups) == 1:

            return self._fallback_linear_split(
                elements,
                book_title,
            )

        chunks = []

        for group in groups:

            chunks.extend(
                self._hierarchical_split(
                    group,
                    book_title,
                    depth + 1,
                )
            )

        return chunks

    # ==================================================================
    # LINEAR SPLIT
    # ==================================================================

    def _fallback_linear_split(
        self,
        elements: List[Dict],
        book_title: str,
    ) -> List[Dict]:

        chunks = []

        current_chunk = []
        current_tokens = 0

        boundaries = {
            "paragraph",
            "heading",
            "image_occurrence",
            "table",
            "caption",
            "list_item",
        }

        for index, element in enumerate(
            elements
        ):

            element_tokens = (
                self._get_element_tokens(
                    element
                )
                + 10
            )

            # ----------------------------------------------------------
            # Large single element.
            # Keep it alone instead of creating broken chunks.
            # ----------------------------------------------------------

            if (
                element_tokens
                > self.max_tokens_per_chunk
                and not current_chunk
            ):

                chunks.append(
                    {
                        "book_title": book_title,
                        "elements": [element],
                    }
                )

                continue

            current_chunk.append(
                element
            )

            current_tokens += element_tokens

            is_boundary = (
                element.get("type")
                in boundaries
            )

            should_split = (
                current_tokens
                >= self.max_tokens_per_chunk
                and is_boundary
                and index < len(elements) - 1
            )

            if should_split:

                chunks.append(
                    {
                        "book_title": book_title,
                        "elements": current_chunk,
                    }
                )

                overlap_count = min(
                    self.overlap_elements,
                    len(current_chunk),
                )

                overlap = (
                    current_chunk[
                        -overlap_count:
                    ]
                    if overlap_count
                    else []
                )

                current_chunk = (
                    overlap.copy()
                )

                current_tokens = sum(
                    self._get_element_tokens(
                        item
                    )
                    + 10
                    for item in current_chunk
                )

        if current_chunk:

            chunks.append(
                {
                    "book_title": book_title,
                    "elements": current_chunk,
                }
            )

        return chunks

    # ==================================================================
    # FORMAT LOGICAL PAYLOAD
    # ==================================================================

    def _format_logical_payload(
        self,
        chunk: Dict[str, Any],
    ) -> str:

        book_title = chunk.get(
            "book_title",
            "Scientific Document",
        )

        elements = chunk.get(
            "elements",
            [],
        )

        pages = sorted(
            {
                e.get("page_number")
                for e in elements
                if e.get("page_number")
                is not None
            }
        )

        if len(pages) > 1:

            page_context = (
                f"Pages {pages[0]}-{pages[-1]}"
            )

        elif pages:

            page_context = (
                f"Page {pages[0]}"
            )

        else:

            page_context = ""

        lines = [
            "TAGTASTE DOCUMENT",
            f"Book: {book_title}",
            page_context,
            "",
            "Extract explicit sensory knowledge.",
            "Keep values attached to their concepts.",
            "Keep table row/column relationships.",
            "Preserve hierarchy.",
            "",
            "CONTENT:",
        ]

        current_path = None

        for element in elements:

            path_nodes = (
                element
                .get(
                    "context",
                    {},
                )
                .get(
                    "path",
                    [],
                )
            )

            path = tuple(
                str(
                    node.get(
                        "text",
                        "",
                    )
                )
                for node in path_nodes
            )

            if path != current_path:

                hierarchy = (
                    " > ".join(path)
                    if path
                    else "General Content"
                )

                lines.append(
                    f"\n[HIERARCHY: {hierarchy}]"
                )

                current_path = path

            element_type = element.get(
                "type",
                "paragraph",
            )

            page = element.get(
                "page_number"
            )

            element_id = element.get(
                "element_id",
                "unknown",
            )

            if element_type in {
                "heading",
                "paragraph",
                "caption",
                "list_item",
                "equation",
                "cross_ref",
                "raw_text",
            }:

                text = str(
                    element.get(
                        "text",
                        "",
                    )
                    or ""
                ).strip()

                if text:

                    lines.append(
                        f"[{element_type} "
                        f"p={page} "
                        f"id={element_id}] "
                        f"{text}"
                    )

            elif element_type == "table":

                lines.append(
                    f"[TABLE p={page} "
                    f"id={element_id}]"
                )

                table_text = (
                    self._render_table_markdown(
                        element.get(
                            "cells",
                            [],
                        )
                    )
                )

                if table_text:
                    lines.append(
                        table_text
                    )

            elif element_type == "image_occurrence":

                lines.append(
                    f"[FIGURE p={page} "
                    f"id={element_id}]"
                )

        return "\n".join(lines)

    # ==================================================================
    # LLM EXTRACTION
    # ==================================================================

    async def _process_logical_unit(
        self,
        chunk_id: str,
        chunk: Dict[str, Any],
    ) -> Dict[str, List[Any]]:

        started = time.perf_counter()

        payload = (
            self._format_logical_payload(
                chunk
            )
        )

        if (
            len(payload.strip())
            < self.MIN_PAYLOAD_LENGTH
        ):

            return self._empty_extraction()

        elements = chunk.get(
            "elements",
            [],
        )

        first_page = (
            elements[0].get(
                "page_number"
            )
            if elements
            else None
        )

        # --------------------------------------------------------------
        # SHORT USER PROMPT
        # --------------------------------------------------------------

        user_prompt = (
            "Extract all explicit knowledge from this "
            "document unit.\n\n"
            "Rules:\n"
            "- Preserve product/sample context.\n"
            "- Preserve sensory attribute context.\n"
            "- Preserve descriptors.\n"
            "- Preserve score/intensity/measurement context.\n"
            "- Preserve scale information.\n"
            "- Preserve table relationships.\n"
            "- Preserve hierarchy.\n"
            "- Do not create floating numeric values.\n"
            "- Do not create floating descriptors.\n"
            "- Do not invent relationships.\n\n"
            f"{payload}"
        )

        for attempt in range(
            self.LLM_MAX_RETRIES + 1
        ):

            try:

                logger.debug(
                    f"LLM unit {chunk_id} "
                    f"started "
                    f"attempt={attempt + 1}"
                )

                # ------------------------------------------------------
                # Timeout this individual operation.
                # ------------------------------------------------------

                completion = await asyncio.wait_for(
                    self.client.beta.chat.completions.parse(
                        model=self.model_name,
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    self._system_prompt
                                ),
                            },
                            {
                                "role": "user",
                                "content": user_prompt,
                            },
                        ],
                        response_format=KnowledgeExtractionPayload,
                        temperature=0.0,
                    ),
                    timeout=90.0,
                )

                message = (
                    completion
                    .choices[0]
                    .message
                )

                result = message.parsed

                if result is None:

                    logger.warning(
                        f"Empty structured result "
                        f"for {chunk_id}"
                    )

                    return (
                        self._empty_extraction()
                    )

                extracted = (
                    self._empty_extraction()
                )

                # ------------------------------------------------------
                # CONCEPTS
                # ------------------------------------------------------

                for concept in result.concepts:

                    data = (
                        concept.model_dump()
                    )

                    data[
                        "hierarchy_context"
                    ] = (
                        data.get(
                            "hierarchy_context"
                        )
                        or "Extracted Content"
                    )

                    data[
                        "source_page"
                    ] = first_page

                    extracted[
                        "concepts"
                    ].append(data)

                # ------------------------------------------------------
                # RELATIONSHIPS
                # ------------------------------------------------------

                for relationship in (
                    result.relationships
                ):

                    data = (
                        relationship.model_dump()
                    )

                    relation_type = str(
                        data.get(
                            "relationship_type",
                            "related_to",
                        )
                        or "related_to"
                    ).strip()

                    if (
                        relation_type
                        not in self.allowed_relationships
                    ):
                        relation_type = (
                            "related_to"
                        )

                    data[
                        "relationship_type"
                    ] = relation_type

                    extracted[
                        "relationships"
                    ].append(data)

                # ------------------------------------------------------
                # SCIENTIFIC RULES
                # ------------------------------------------------------

                extracted[
                    "scientific_rules"
                ] = [
                    item.model_dump()
                    for item
                    in result.scientific_rules
                ]

                # ------------------------------------------------------
                # PROCEDURES
                # ------------------------------------------------------

                extracted[
                    "procedures"
                ] = [
                    item.model_dump()
                    for item
                    in result.procedures
                ]

                elapsed = (
                    time.perf_counter()
                    - started
                )

                logger.debug(
                    f"LLM unit {chunk_id} "
                    f"completed in "
                    f"{elapsed:.2f}s"
                )

                return extracted

            except asyncio.TimeoutError:

                logger.warning(
                    f"LLM unit {chunk_id} "
                    f"timed out "
                    f"attempt={attempt + 1}"
                )

                if (
                    attempt
                    >= self.LLM_MAX_RETRIES
                ):
                    return (
                        self._empty_extraction()
                    )

                await asyncio.sleep(
                    self.LLM_RETRY_BASE_DELAY
                )

            except Exception as exc:

                error_text = str(exc)

                logger.warning(
                    f"LLM unit {chunk_id} "
                    f"failed "
                    f"attempt={attempt + 1}: "
                    f"{error_text}"
                )

                # ------------------------------------------------------
                # Only retry likely transient errors.
                # ------------------------------------------------------

                transient = (
                    "timeout" in error_text.lower()
                    or "timed out" in error_text.lower()
                    or "429" in error_text
                    or "rate limit" in error_text.lower()
                    or "503" in error_text
                    or "502" in error_text
                    or "504" in error_text
                    or "connection" in error_text.lower()
                )

                if (
                    not transient
                    or attempt
                    >= self.LLM_MAX_RETRIES
                ):

                    logger.error(
                        f"Permanent extraction failure "
                        f"for {chunk_id}: "
                        f"{error_text}"
                    )

                    return (
                        self._empty_extraction()
                    )

                await asyncio.sleep(
                    self.LLM_RETRY_BASE_DELAY
                    * (attempt + 1)
                )

        return self._empty_extraction()

    # ==================================================================
    # NORMALIZE KEY
    # ==================================================================

    def _normalize_key(
        self,
        name: str,
    ) -> str:

        if not name:
            return "unknown"

        value = str(
            name
        ).strip().lower()

        value = re.sub(
            r"[^a-z0-9]+",
            "",
            value,
        )

        if (
            value.endswith("s")
            and not value.endswith("ss")
            and len(value) > 3
        ):
            value = value[:-1]

        return value or "unknown"

    # ==================================================================
    # METADATA FILTER
    # ==================================================================

    def _is_metadata_concept(
        self,
        name: str,
    ) -> bool:

        key = self._normalize_key(
            name
        )

        if not key:
            return True

        return any(
            keyword in key
            for keyword
            in self.METADATA_KEYWORDS
        )

    # ==================================================================
    # GLOBAL GRAPH STITCHING
    # ==================================================================

    def _stitch_global_graph(
        self,
        raw_concepts: List[Dict[str, Any]],
        raw_relationships: List[Dict[str, Any]],
    ) -> Tuple[
        List[Dict[str, Any]],
        List[Dict[str, Any]],
    ]:

        merged: Dict[
            str,
            Dict[str, Any],
        ] = {}

        # --------------------------------------------------------------
        # CONCEPTS
        # --------------------------------------------------------------

        for raw in raw_concepts:

            if not isinstance(
                raw,
                dict,
            ):
                continue

            concept = dict(raw)

            name = str(
                concept.get(
                    "canonical_name",
                    "",
                )
                or ""
            ).strip()

            if not name:
                continue

            if self._is_metadata_concept(
                name
            ):
                continue

            key = self._normalize_key(
                name
            )

            if key == "unknown":
                continue

            category = concept.get(
                "category"
            )

            if (
                category
                not in self.ontology_categories
            ):

                concept[
                    "category"
                ] = "Entity"

            # ----------------------------------------------------------
            # LIST NORMALIZATION
            # ----------------------------------------------------------

            synonyms = concept.get(
                "synonyms",
                [],
            )

            if not isinstance(
                synonyms,
                list,
            ):
                synonyms = [
                    str(synonyms)
                ]

            keywords = concept.get(
                "keywords",
                [],
            )

            if not isinstance(
                keywords,
                list,
            ):
                keywords = [
                    str(keywords)
                ]

            concept[
                "synonyms"
            ] = sorted(
                {
                    str(x).strip()
                    for x in synonyms
                    if str(x).strip()
                }
            )

            concept[
                "keywords"
            ] = sorted(
                {
                    str(x).strip()
                    for x in keywords
                    if str(x).strip()
                }
            )[:10]

            # ----------------------------------------------------------
            # INSERT
            # ----------------------------------------------------------

            if key not in merged:

                concept[
                    "canonical_name"
                ] = name

                merged[key] = concept

                continue

            # ----------------------------------------------------------
            # MERGE
            # ----------------------------------------------------------

            existing = merged[key]

            existing_synonyms = set(
                existing.get(
                    "synonyms",
                    [],
                )
            )

            existing_synonyms.update(
                concept.get(
                    "synonyms",
                    [],
                )
            )

            existing[
                "synonyms"
            ] = sorted(
                existing_synonyms
            )

            existing_keywords = set(
                existing.get(
                    "keywords",
                    [],
                )
            )

            existing_keywords.update(
                concept.get(
                    "keywords",
                    [],
                )
            )

            existing[
                "keywords"
            ] = sorted(
                existing_keywords
            )[:10]

            current_hierarchy = str(
                concept.get(
                    "hierarchy_context",
                    "",
                )
                or ""
            ).strip()

            existing_hierarchy = str(
                existing.get(
                    "hierarchy_context",
                    "",
                )
                or ""
            ).strip()

            if (
                current_hierarchy
                and current_hierarchy
                not in existing_hierarchy
            ):

                existing[
                    "hierarchy_context"
                ] = (
                    f"{existing_hierarchy} | "
                    f"{current_hierarchy}"
                    if existing_hierarchy
                    else current_hierarchy
                )

        # --------------------------------------------------------------
        # RELATIONSHIPS
        # --------------------------------------------------------------

        valid_keys = set(
            merged.keys()
        )

        clean_relationships = []

        seen = set()

        for raw in raw_relationships:

            if not isinstance(
                raw,
                dict,
            ):
                continue

            relationship = dict(raw)

            source = str(
                relationship.get(
                    "source_concept",
                    "",
                )
                or ""
            ).strip()

            target = str(
                relationship.get(
                    "target_concept",
                    "",
                )
                or ""
            ).strip()

            source_key = (
                self._normalize_key(
                    source
                )
            )

            target_key = (
                self._normalize_key(
                    target
                )
            )

            if (
                source_key
                not in valid_keys
                or target_key
                not in valid_keys
            ):
                continue

            if source_key == target_key:
                continue

            relation_type = str(
                relationship.get(
                    "relationship_type",
                    "related_to",
                )
                or "related_to"
            ).strip()

            if (
                relation_type
                not in self.allowed_relationships
            ):
                relation_type = (
                    "related_to"
                )

            relationship[
                "source_concept"
            ] = merged[
                source_key
            ][
                "canonical_name"
            ]

            relationship[
                "target_concept"
            ] = merged[
                target_key
            ][
                "canonical_name"
            ]

            relationship[
                "relationship_type"
            ] = relation_type

            signature = (
                source_key,
                relation_type,
                target_key,
            )

            if signature in seen:
                continue

            seen.add(signature)

            clean_relationships.append(
                relationship
            )

        return (
            list(merged.values()),
            clean_relationships,
        )

    # ==================================================================
    # METADATA
    # ==================================================================

    def _read_metadata(
        self,
        metadata_path: Path,
    ) -> Dict[str, Any]:

        if not metadata_path.exists():
            return {}

        try:

            with open(
                metadata_path,
                "r",
                encoding="utf-8",
            ) as file:

                value = json.load(file)

                if isinstance(
                    value,
                    dict,
                ):
                    return value

        except Exception as exc:

            logger.warning(
                f"Could not read metadata "
                f"{metadata_path}: {exc}"
            )

        return {}

    # ==================================================================
    # ATOMIC JSON
    # ==================================================================

    def _atomic_write_json(
        self,
        path: Path,
        data: Dict[str, Any],
    ) -> None:

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp = path.with_suffix(
            path.suffix + ".tmp"
        )

        with open(
            temp,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                data,
                file,
                indent=2,
                ensure_ascii=False,
            )

            file.flush()

        temp.replace(path)

    # ==================================================================
    # STATUS
    # ==================================================================

    def _update_metadata_status(
        self,
        metadata_path: Path,
        document_id: str,
        status: str,
    ) -> None:

        try:

            metadata = self._read_metadata(
                metadata_path
            )

            if not metadata:
                return

            metadata[
                "pipeline_status"
            ] = status

            if status == "KNOWLEDGE_EXTRACTION_RUNNING":

                metadata[
                    "next_step"
                ] = None

            elif status == "KNOWLEDGE_EXTRACTED":

                metadata[
                    "next_step"
                ] = (
                    f"{settings.API_V1_STR}"
                    f"/documents/{document_id}"
                    f"/knowledge"
                )

            elif status == "KNOWLEDGE_EXTRACTION_FAILED":

                metadata[
                    "next_step"
                ] = None

            self._atomic_write_json(
                metadata_path,
                metadata,
            )

        except Exception as exc:

            logger.warning(
                f"Could not update metadata "
                f"for {document_id}: {exc}"
            )

    # ==================================================================
    # MASTER PIPELINE
    # ==================================================================

    async def extract_knowledge(
        self,
        document_id: str,
    ) -> Dict[str, Any]:

        started_at = time.perf_counter()

        processed_base = (
            self.processed_dir
            / document_id
        )

        normalized_path = (
            processed_base
            / "normalized_elements.jsonl"
        )

        metadata_path = (
            self.raw_dir
            / document_id
            / "metadata.json"
        )

        output_path = (
            processed_base
            / "extracted_knowledge.json"
        )

        logger.info(
            f"Starting fast TagTaste "
            f"knowledge extraction "
            f"for {document_id}"
        )

        try:

            # ==========================================================
            # 1. STATUS
            # ==========================================================

            self._update_metadata_status(
                metadata_path,
                document_id,
                "KNOWLEDGE_EXTRACTION_RUNNING",
            )

            # ==========================================================
            # 2. WAIT FOR STRUCTURAL EXTRACTION
            # ==========================================================

            await self._wait_for_normalized_file(
                normalized_path,
                document_id,
            )

            # ==========================================================
            # 3. METADATA
            # ==========================================================

            metadata = self._read_metadata(
                metadata_path
            )

            book_title = metadata.get(
                "title",
                "Scientific Document",
            )

            # ==========================================================
            # 4. LOAD ELEMENTS
            # ==========================================================

            elements = (
                self._load_normalized_elements(
                    normalized_path
                )
            )

            if not elements:

                empty_artifact = {
                    "document_id": document_id,
                    "concepts": [],
                    "relationships": [],
                    "scientific_rules": [],
                    "procedures": [],
                }

                self._atomic_write_json(
                    output_path,
                    empty_artifact,
                )

                self._update_metadata_status(
                    metadata_path,
                    document_id,
                    "KNOWLEDGE_EXTRACTED",
                )

                return {
                    "document_id": document_id,
                    "pipeline_status":
                        "KNOWLEDGE_EXTRACTED",
                    "extracted_stats": {
                        "raw_concepts_found": 0,
                        "clean_concepts_saved": 0,
                        "relationships_extracted": 0,
                    },
                    "knowledge_artifact_path":
                        str(
                            output_path.relative_to(
                                settings.BASE_DIR
                            )
                        ),
                }

            logger.info(
                f"Loaded {len(elements)} "
                f"normalized elements "
                f"for {document_id}"
            )

            # ==========================================================
            # 5. CACHE
            # ==========================================================

            cache_start = time.perf_counter()

            self._prepare_element_cache(
                elements
            )

            logger.info(
                f"Cache prepared in "
                f"{time.perf_counter() - cache_start:.2f}s"
            )

            # ==========================================================
            # 6. CHUNK
            # ==========================================================

            split_start = time.perf_counter()

            logical_units = (
                self._hierarchical_split(
                    elements,
                    book_title,
                )
            )

            split_elapsed = (
                time.perf_counter()
                - split_start
            )

            total_units = len(
                logical_units
            )

            logger.info(
                f"Created {total_units} "
                f"logical units in "
                f"{split_elapsed:.2f}s "
                f"with target chunk="
                f"{self.max_tokens_per_chunk} "
                f"tokens and concurrency="
                f"{self.max_concurrent_requests}"
            )

            # ==========================================================
            # 7. CONCURRENT LLM EXTRACTION
            # ==========================================================

            semaphore = asyncio.Semaphore(
                self.max_concurrent_requests
            )

            async def process_unit(
                index: int,
                unit: Dict[str, Any],
            ):

                async with semaphore:

                    return await (
                        self._process_logical_unit(
                            f"unit_{index}",
                            unit,
                        )
                    )

            tasks = [
                asyncio.create_task(
                    process_unit(
                        index,
                        unit,
                    )
                )
                for index, unit
                in enumerate(
                    logical_units
                )
            ]

            raw_concepts = []
            raw_relationships = []
            scientific_rules = []
            procedures = []

            completed = 0

            llm_start = time.perf_counter()

            for task in asyncio.as_completed(
                tasks
            ):

                try:

                    result = await task

                except Exception as exc:

                    logger.error(
                        f"Unexpected unit failure "
                        f"for {document_id}: "
                        f"{exc}",
                        exc_info=True,
                    )

                    result = (
                        self._empty_extraction()
                    )

                completed += 1

                raw_concepts.extend(
                    result.get(
                        "concepts",
                        [],
                    )
                )

                raw_relationships.extend(
                    result.get(
                        "relationships",
                        [],
                    )
                )

                scientific_rules.extend(
                    result.get(
                        "scientific_rules",
                        [],
                    )
                )

                procedures.extend(
                    result.get(
                        "procedures",
                        [],
                    )
                )

                if (
                    completed == 1
                    or completed % 10 == 0
                    or completed == total_units
                ):

                    elapsed = (
                        time.perf_counter()
                        - llm_start
                    )

                    rate = (
                        completed / elapsed
                        if elapsed > 0
                        else 0
                    )

                    remaining = (
                        total_units
                        - completed
                    )

                    eta = (
                        remaining / rate
                        if rate > 0
                        else 0
                    )

                    logger.info(
                        f"Knowledge extraction "
                        f"{document_id}: "
                        f"{completed}/"
                        f"{total_units} "
                        f"| {rate:.2f} units/sec "
                        f"| ETA {eta:.1f}s"
                    )

            llm_elapsed = (
                time.perf_counter()
                - llm_start
            )

            logger.info(
                f"LLM extraction completed "
                f"for {document_id} in "
                f"{llm_elapsed:.2f}s"
            )

            # ==========================================================
            # 8. GRAPH STITCHING
            # ==========================================================

            stitch_start = time.perf_counter()

            (
                clean_concepts,
                clean_relationships,
            ) = self._stitch_global_graph(
                raw_concepts,
                raw_relationships,
            )

            stitch_elapsed = (
                time.perf_counter()
                - stitch_start
            )

            logger.info(
                f"Graph stitching completed "
                f"in {stitch_elapsed:.2f}s"
            )

            # ==========================================================
            # 9. FINAL ARTIFACT
            # ==========================================================

            master_knowledge = {
                "document_id": document_id,
                "concepts": clean_concepts,
                "relationships": clean_relationships,
                "scientific_rules": scientific_rules,
                "procedures": procedures,
            }

            # ==========================================================
            # 10. ATOMIC SAVE
            # ==========================================================

            self._atomic_write_json(
                output_path,
                master_knowledge,
            )

            # ==========================================================
            # 11. STATUS
            # ==========================================================

            self._update_metadata_status(
                metadata_path,
                document_id,
                "KNOWLEDGE_EXTRACTED",
            )

            # ==========================================================
            # 12. FINAL
            # ==========================================================

            total_elapsed = (
                time.perf_counter()
                - started_at
            )

            logger.info(
                f"TagTaste knowledge extraction "
                f"completed for {document_id} "
                f"in {total_elapsed:.2f}s | "
                f"units={total_units} | "
                f"raw_concepts="
                f"{len(raw_concepts)} | "
                f"clean_concepts="
                f"{len(clean_concepts)} | "
                f"relationships="
                f"{len(clean_relationships)}"
            )

            return {
                "document_id": document_id,
                "pipeline_status":
                    "KNOWLEDGE_EXTRACTED",
                "extracted_stats": {
                    "raw_concepts_found":
                        len(raw_concepts),
                    "clean_concepts_saved":
                        len(clean_concepts),
                    "relationships_extracted":
                        len(clean_relationships),
                },
                "knowledge_artifact_path":
                    str(
                        output_path.relative_to(
                            settings.BASE_DIR
                        )
                    ),
            }

        # ==============================================================
        # CONTROLLED FAILURE
        # ==============================================================

        except (
            DocumentNotFoundError,
            ProcessingError,
            StorageError,
        ) as exc:

            logger.error(
                f"Knowledge extraction could not "
                f"complete for {document_id}: "
                f"{exc}",
                exc_info=True,
            )

            self._update_metadata_status(
                metadata_path,
                document_id,
                "KNOWLEDGE_EXTRACTION_FAILED",
            )

            return {
                "document_id": document_id,
                "pipeline_status":
                    "KNOWLEDGE_EXTRACTION_FAILED",
                "extracted_stats": {
                    "raw_concepts_found": 0,
                    "clean_concepts_saved": 0,
                    "relationships_extracted": 0,
                },
                "knowledge_artifact_path": None,
            }

        except Exception as exc:

            logger.error(
                f"Knowledge extraction failed "
                f"for {document_id}: "
                f"{exc}",
                exc_info=True,
            )

            self._update_metadata_status(
                metadata_path,
                document_id,
                "KNOWLEDGE_EXTRACTION_FAILED",
            )

            return {
                "document_id": document_id,
                "pipeline_status":
                    "KNOWLEDGE_EXTRACTION_FAILED",
                "extracted_stats": {
                    "raw_concepts_found": 0,
                    "clean_concepts_saved": 0,
                    "relationships_extracted": 0,
                },
                "knowledge_artifact_path": None,
            }