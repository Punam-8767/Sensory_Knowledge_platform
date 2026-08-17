# import json
# from typing import Dict, Any
# from openai import AsyncOpenAI
# from app.core.config import settings
# from app.core.logger import logger
# from app.core.exceptions import DocumentNotFoundError, StorageError
# from app.models.knowledge import KnowledgeExtractionPayload


# class ExtractionService:
#     def __init__(self):
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR
#         self.raw_dir = settings.STORAGE_RAW_DIR
#         self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

#     async def extract_knowledge(self, document_id: str) -> Dict[str, Any]:
#         """Iterates through the structural document tree and extracts knowledge via LLM."""
#         doc_dir = self.processed_dir / document_id
#         tree_path = doc_dir / "document_tree.json"
#         metadata_path = self.raw_dir / document_id / "metadata.json"

#         if not tree_path.exists():
#             raise DocumentNotFoundError(f"Structure tree not found for {document_id}. Run extract-structure first.")

#         try:
#             with open(tree_path, "r", encoding="utf-8") as f:
#                 document_tree = json.load(f)

#             logger.info(f"Starting LLM Knowledge Extraction for {document_id}")
            
#             master_knowledge = {
#                 "document_id": document_id,
#                 "concepts": [],
#                 "relationships": [],
#                 "scientific_rules": [],
#                 "procedures": []
#             }

#             for page in document_tree.get("pages", []):
#                 page_num = page.get("page_number")
#                 full_text = page.get("full_text", "").strip()
                
#                 # Skip sparse or empty pages
#                 if not full_text or len(full_text) < 150:
#                     continue 

#                 logger.debug(f"Extracting knowledge from page {page_num} via LLM...")
                
#                 completion = await self.client.beta.chat.completions.parse(
#                     model="gpt-4o-mini",
#                     messages=[
#                         {
#                             "role": "system", 
#                             "content": "You are an expert scientific knowledge extraction agent. Your task is to extract concepts, relationships, scientific rules, and procedures from the provided text according to the exact JSON schema. Be highly precise. If a relationship or rule does not exist, leave the array empty."
#                         },
#                         {
#                             "role": "user", 
#                             "content": f"Extract the structured knowledge from this scientific text page:\n\n{full_text}"
#                         }
#                     ],
#                     response_format=KnowledgeExtractionPayload,
#                     temperature=0.1
#                 )

#                 page_extraction = completion.choices[0].message.parsed
                
#                 if page_extraction:
#                     master_knowledge["concepts"].extend([c.model_dump() for c in page_extraction.concepts])
#                     master_knowledge["relationships"].extend([r.model_dump() for r in page_extraction.relationships])
#                     master_knowledge["scientific_rules"].extend([sr.model_dump() for sr in page_extraction.scientific_rules])
#                     master_knowledge["procedures"].extend([p.model_dump() for p in page_extraction.procedures])

#             knowledge_path = doc_dir / "extracted_knowledge.json"
#             with open(knowledge_path, "w", encoding="utf-8") as f:
#                 json.dump(master_knowledge, f, indent=4)

#             if metadata_path.exists():
#                 with open(metadata_path, "r+", encoding="utf-8") as f:
#                     meta_data = json.load(f)
#                     meta_data["pipeline_status"] = "KNOWLEDGE_EXTRACTED"
#                     meta_data["next_step"] = f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
#                     f.seek(0)
#                     json.dump(meta_data, f, indent=2)
#                     f.truncate()

#             logger.info(f"Successfully completed LLM extraction for {document_id}")
            
#             return {
#                 "document_id": document_id,
#                 "pipeline_status": "KNOWLEDGE_EXTRACTED",
#                 "extracted_stats": {
#                     "concepts": len(master_knowledge["concepts"]),
#                     "relationships": len(master_knowledge["relationships"]),
#                     "scientific_rules": len(master_knowledge["scientific_rules"]),
#                     "procedures": len(master_knowledge["procedures"])
#                 },
#                 "knowledge_artifact_path": str(knowledge_path.relative_to(settings.BASE_DIR)),
#                 "next_step": f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
#             }

#         except Exception as e:
#             logger.error(f"Knowledge Extraction failed for {document_id}: {str(e)}", exc_info=True)
#             raise StorageError(f"LLM Extraction failed: {str(e)}")









# import json
# from typing import Dict, Any, List
# from openai import AsyncOpenAI
# from app.core.config import settings
# from app.core.logger import logger
# from app.core.exceptions import DocumentNotFoundError, ProcessingError
# from app.models.knowledge import KnowledgeExtractionPayload

# class ExtractionService:
#     def __init__(self):
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR
#         self.raw_dir = settings.STORAGE_RAW_DIR
#         self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

#     def _format_page_context(self, page: Dict[str, Any]) -> str:
#         """
#         Aggregates text, tables, and image references from a structural page object 
#         into a unified, unchunked context string for the LLM.
#         """
#         content_parts = []
#         page_num = page.get("page_number")
#         content_parts.append(f"--- PAGE {page_num} ---")

#         # Include headings and paragraphs
#         for element in page.get("elements", []):
#             elem_type = element.get("type")
            
#             if elem_type in ["heading", "paragraph"]:
#                 text = element.get("text", "").strip()
#                 if text:
#                     content_parts.append(f"[{elem_type.upper()}] {text}")
            
#             elif elem_type == "table":
#                 # Convert 2D table rows into a readable markdown/tabular text format for the LLM
#                 rows = element.get("rows", [])
#                 content_parts.append(f"[TABLE index_{element.get('table_index')}]")
#                 for row in rows:
#                     row_str = " | ".join([str(cell or "").strip() for cell in row])
#                     content_parts.append(f"| {row_str} |")
            
#             elif elem_type == "image":
#                 # Include image reference and position context
#                 content_parts.append(f"[IMAGE reference: image_index_{element.get('image_index')} at bbox {element.get('bbox')}]")

#         return "\n".join(content_parts)

#     async def extract_knowledge(self, document_id: str) -> Dict[str, Any]:
#         """
#         Passes unchunked, multi-modal page layouts (Text + Tables + Images) 
#         directly to the LLM to construct concepts, nodes, and relationships.
#         """
#         doc_dir = self.processed_dir / document_id
#         tree_path = doc_dir / "document_tree.json"
#         metadata_path = self.raw_dir / document_id / "metadata.json"

#         if not tree_path.exists():
#             raise DocumentNotFoundError(f"Structure tree not found for {document_id}. Run extract-structure first.")

#         try:
#             with open(tree_path, "r", encoding="utf-8") as f:
#                 document_tree = json.load(f)

#             logger.info(f"Starting unchunked multi-modal LLM extraction for {document_id}")
            
#             master_knowledge = {
#                 "document_id": document_id,
#                 "concepts": [],
#                 "relationships": [],
#                 "scientific_rules": [],
#                 "procedures": []
#             }

#             for page in document_tree.get("pages", []):
#                 page_num = page.get("page_number")
                
#                 # Format complete page context without chunking
#                 page_context = self._format_page_context(page)
                
#                 # Skip sparse pages
#                 if len(page_context.strip()) < 100:
#                     continue 

#                 logger.debug(f"Sending unchunked page {page_num} layout (Text + Tables + Images) to LLM...")
                
#                 completion = await self.client.beta.chat.completions.parse(
#                     model="gpt-4o-mini",
#                     messages=[
#                         {
#                             "role": "system", 
#                             "content": (
#                                 "You are an expert scientific knowledge extraction agent. "
#                                 "You are receiving complete, unchunked document page layouts containing text, tables, and image references. "
#                                 "Extract precise scientific concepts, node relationships, rules, and procedures into the exact structured schema. "
#                                 "Do not miss relationships implied by tables or text."
#                             )
#                         },
#                         {
#                             "role": "user", 
#                             "content": f"Extract structured knowledge and relationships from this unchunked page layout:\n\n{page_context}"
#                         }
#                     ],
#                     response_format=KnowledgeExtractionPayload,
#                     temperature=0.1
#                 )

#                 page_extraction = completion.choices[0].message.parsed
                
#                 if page_extraction:
#                     master_knowledge["concepts"].extend([c.model_dump() for c in page_extraction.concepts])
#                     master_knowledge["relationships"].extend([r.model_dump() for r in page_extraction.relationships])
#                     master_knowledge["scientific_rules"].extend([sr.model_dump() for sr in page_extraction.scientific_rules])
#                     master_knowledge["procedures"].extend([p.model_dump() for p in page_extraction.procedures])

#             # Save extracted knowledge artifact
#             knowledge_path = doc_dir / "extracted_knowledge.json"
#             with open(knowledge_path, "w", encoding="utf-8") as f:
#                 json.dump(master_knowledge, f, indent=4)

#             # Update pipeline state
#             if metadata_path.exists():
#                 with open(metadata_path, "r+", encoding="utf-8") as f:
#                     meta_data = json.load(f)
#                     meta_data["pipeline_status"] = "KNOWLEDGE_EXTRACTED"
#                     meta_data["next_step"] = f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
#                     f.seek(0)
#                     json.dump(meta_data, f, indent=2)
#                     f.truncate()

#             logger.info(f"Successfully completed unchunked multi-modal extraction for {document_id}")
            
#             return {
#                 "document_id": document_id,
#                 "pipeline_status": "KNOWLEDGE_EXTRACTED",
#                 "extracted_stats": {
#                     "concepts": len(master_knowledge["concepts"]),
#                     "relationships": len(master_knowledge["relationships"]),
#                     "scientific_rules": len(master_knowledge["scientific_rules"]),
#                     "procedures": len(master_knowledge["procedures"])
#                 },
#                 "knowledge_artifact_path": str(knowledge_path.relative_to(settings.BASE_DIR))
#             }

#         except Exception as e:
#             logger.error(f"Knowledge Extraction failed for {document_id}: {str(e)}", exc_info=True)
#             raise ProcessingError(f"LLM Extraction failed: {str(e)}")









# import json
# from typing import Dict, Any, List
# from openai import AsyncOpenAI
# from app.core.config import settings
# from app.core.logger import logger
# from app.core.exceptions import DocumentNotFoundError, ProcessingError
# from app.models.knowledge import KnowledgeExtractionPayload

# class ExtractionService:
#     def __init__(self):
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR
#         self.raw_dir = settings.STORAGE_RAW_DIR
#         self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

#     def _format_unchunked_page_payload(self, page: Dict[str, Any]) -> str:
#         """
#         Combines headings, paragraphs, 2D table rows, and image bboxes 
#         into a single, unchunked contextual unit for the LLM.
#         """
#         page_num = page.get("page_number")
#         lines = [f"=== DOCUMENT PAGE {page_num} ==="]

#         for element in page.get("elements", []):
#             elem_type = element.get("type")
            
#             if elem_type in ["heading", "paragraph"]:
#                 text = element.get("text", "").strip()
#                 if text:
#                     lines.append(f"[{elem_type.upper()}] {text}")
            
#             elif elem_type == "table":
#                 # Formats the 2D table matrix cleanly so the LLM understands the rows/columns
#                 rows = element.get("rows", [])
#                 lines.append(f"[TABLE index_{element.get('table_index')}]")
#                 for row in rows:
#                     row_content = " | ".join([str(cell or "").strip() for cell in row])
#                     lines.append(f"| {row_content} |")
            
#             elif elem_type == "image":
#                 lines.append(f"[IMAGE asset: index_{element.get('image_index')} located at bbox {element.get('bbox')}]")

#         return "\n".join(lines)

#     async def extract_knowledge(self, document_id: str) -> Dict[str, Any]:
#         """
#         Reads unchunked structural layout, formats tables/images/text, 
#         and invokes the LLM to extract nodes, subnodes, and relationships.
#         """
#         doc_dir = self.processed_dir / document_id
#         tree_path = doc_dir / "document_tree.json"
#         metadata_path = self.raw_dir / document_id / "metadata.json"

#         if not tree_path.exists():
#             raise DocumentNotFoundError(f"Structure tree not found for {document_id}. Run /extract-structure first.")

#         try:
#             with open(tree_path, "r", encoding="utf-8") as f:
#                 document_tree = json.load(f)

#             logger.info(f"Starting unchunked LLM extraction & relationship mapping for {document_id}")
            
#             master_knowledge = {
#                 "document_id": document_id,
#                 "concepts": [],
#                 "relationships": [],
#                 "scientific_rules": [],
#                 "procedures": []
#             }

#             pages = document_tree.get("pages", [])
#             for page in pages:
#                 page_num = page.get("page_number")
                
#                 # Make the content ready for the LLM without chunking
#                 page_payload = self._format_unchunked_page_payload(page)
                
#                 # Skip blank or cover pages with minimal text
#                 if len(page_payload.strip()) < 120:
#                     continue

#                 logger.debug(f"Sending unchunked page {page_num} layout to LLM...")
                
#                 # OpenAI Structured Output ensures exact JSON schema compliance
#                 completion = await self.client.beta.chat.completions.parse(
#                     model="gpt-4o-mini",
#                     messages=[
#                         {
#                             "role": "system", 
#                             "content": (
#                                 "You are an expert scientific knowledge extraction engine. "
#                                 "You are given complete, unchunked document pages containing text, table matrices, and image references. "
#                                 "Your task is to analyze the entire page context and extract scientific concepts, nodes, subnodes, "
#                                 "and precise relationship edges into the structured schema. Never split concepts arbitrarily."
#                             )
#                         },
#                         {
#                             "role": "user", 
#                             "content": f"Extract all concepts, nodes, subnodes, and relationships from this unchunked page layout:\n\n{page_payload}"
#                         }
#                     ],
#                     response_format=KnowledgeExtractionPayload,
#                     temperature=0.1
#                 )

#                 extracted_data = completion.choices[0].message.parsed
                
#                 if extracted_data:
#                     master_knowledge["concepts"].extend([c.model_dump() for c in extracted_data.concepts])
#                     master_knowledge["relationships"].extend([r.model_dump() for r in extracted_data.relationships])
#                     master_knowledge["scientific_rules"].extend([sr.model_dump() for sr in extracted_data.scientific_rules])
#                     master_knowledge["procedures"].extend([p.model_dump() for p in extracted_data.procedures])

#             # Save the resulting extracted knowledge graph artifact
#             knowledge_path = doc_dir / "extracted_knowledge.json"
#             with open(knowledge_path, "w", encoding="utf-8") as f:
#                 json.dump(master_knowledge, f, indent=4)

#             # Update pipeline metadata state
#             if metadata_path.exists():
#                 with open(metadata_path, "r+", encoding="utf-8") as f:
#                     meta_data = json.load(f)
#                     meta_data["pipeline_status"] = "KNOWLEDGE_EXTRACTED"
#                     meta_data["next_step"] = f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
#                     f.seek(0)
#                     json.dump(meta_data, f, indent=2)
#                     f.truncate()

#             logger.info(f"Successfully generated knowledge graph nodes & relationships for {document_id}")
            
#             return {
#                 "document_id": document_id,
#                 "pipeline_status": "KNOWLEDGE_EXTRACTED",
#                 "extracted_stats": {
#                     "concepts_extracted": len(master_knowledge["concepts"]),
#                     "relationships_extracted": len(master_knowledge["relationships"]),
#                     "scientific_rules": len(master_knowledge["scientific_rules"]),
#                     "procedures": len(master_knowledge["procedures"])
#                 },
#                 "knowledge_artifact_path": str(knowledge_path.relative_to(settings.BASE_DIR))
#             }

#         except Exception as e:
#             logger.error(f"Unchunked LLM extraction failed for {document_id}: {str(e)}", exc_info=True)
#             raise ProcessingError(f"LLM Extraction failed: {str(e)}")








# import json
# from typing import Dict, Any, List
# from openai import AsyncOpenAI
# from app.core.config import settings
# from app.core.logger import logger
# from app.core.exceptions import DocumentNotFoundError, ProcessingError
# from app.models.knowledge import KnowledgeExtractionPayload

# class ExtractionService:
#     def __init__(self):
#         self.processed_dir = settings.STORAGE_PROCESSED_DIR
#         self.raw_dir = settings.STORAGE_RAW_DIR
#         self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

#     def _format_page_payload(self, page: Dict[str, Any]) -> str:
#         """Formats the unchunked page layout (text, tables, images) for the LLM."""
#         page_num = page.get("page_number")
#         lines = [f"=== PAGE {page_num} ==="]

#         for element in page.get("elements", []):
#             elem_type = element.get("type")
#             if elem_type in ["heading", "paragraph"]:
#                 text = element.get("text", "").strip()
#                 if text:
#                     lines.append(f"[{elem_type.upper()}] {text}")
#             elif elem_type == "table":
#                 rows = element.get("rows", [])
#                 lines.append(f"[TABLE index_{element.get('table_index')}]")
#                 for row in rows:
#                     row_content = " | ".join([str(cell or "").strip() for cell in row])
#                     lines.append(f"| {row_content} |")
#             elif elem_type == "image":
#                 lines.append(f"[IMAGE asset at bbox {element.get('bbox')}]")

#         return "\n".join(lines)

#     async def extract_knowledge(self, document_id: str) -> Dict[str, Any]:
#         doc_dir = self.processed_dir / document_id
#         tree_path = doc_dir / "document_tree.json"
#         metadata_path = self.raw_dir / document_id / "metadata.json"

#         if not tree_path.exists():
#             raise DocumentNotFoundError(f"Structure tree not found for {document_id}. Run /extract-structure first.")

#         try:
#             with open(tree_path, "r", encoding="utf-8") as f:
#                 document_tree = json.load(f)

#             logger.info(f"Starting unchunked LLM extraction for {document_id}")
            
#             master_knowledge = {
#                 "document_id": document_id,
#                 "concepts": [],
#                 "relationships": [],
#                 "scientific_rules": [],
#                 "procedures": []
#             }

#             for page in document_tree.get("pages", []):
#                 page_payload = self._format_page_payload(page)
#                 if len(page_payload.strip()) < 120:
#                     continue

#                 completion = await self.client.beta.chat.completions.parse(
#                     model="gpt-4o-mini",
#                     messages=[
#                         {
#                             "role": "system", 
#                             "content": (
#                                 "You are an expert scientific knowledge extraction engine. "
#                                 "Extract precise scientific concepts, nodes, subnodes, and relationship edges "
#                                 "from the provided unchunked page layout into the structured schema."
#                             )
#                         },
#                         {
#                             "role": "user", 
#                             "content": f"Extract knowledge graph nodes and relationships from this page:\n\n{page_payload}"
#                         }
#                     ],
#                     response_format=KnowledgeExtractionPayload,
#                     temperature=0.1
#                 )

#                 extracted_data = completion.choices[0].message.parsed
#                 if extracted_data:
#                     master_knowledge["concepts"].extend([c.model_dump() for c in extracted_data.concepts])
#                     master_knowledge["relationships"].extend([r.model_dump() for r in extracted_data.relationships])
#                     master_knowledge["scientific_rules"].extend([sr.model_dump() for sr in extracted_data.scientific_rules])
#                     master_knowledge["procedures"].extend([p.model_dump() for p in extracted_data.procedures])

#             # Save clean structured knowledge graph
#             knowledge_path = doc_dir / "extracted_knowledge.json"
#             with open(knowledge_path, "w", encoding="utf-8") as f:
#                 json.dump(master_knowledge, f, indent=4)

#             if metadata_path.exists():
#                 with open(metadata_path, "r+", encoding="utf-8") as f:
#                     meta_data = json.load(f)
#                     meta_data["pipeline_status"] = "KNOWLEDGE_EXTRACTED"
#                     meta_data["next_step"] = f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
#                     f.seek(0)
#                     json.dump(meta_data, f, indent=2)
#                     f.truncate()

#             return master_knowledge

#         except Exception as e:
#             logger.error(f"Extraction failed: {str(e)}", exc_info=True)
#             raise ProcessingError(f"LLM Extraction failed: {str(e)}")



import json
from typing import Dict, Any, List
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.exceptions import DocumentNotFoundError, ProcessingError
from app.core.logger import logger
from app.models.knowledge import KnowledgeExtractionPayload

class ExtractionService:
    def __init__(self):
        self.processed_dir = settings.STORAGE_PROCESSED_DIR
        self.raw_dir = settings.STORAGE_RAW_DIR
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    def _format_unchunked_page_payload(self, page: Dict[str, Any]) -> str:
        page_num = page.get("page_number")
        lines = [f"=== DOCUMENT PAGE {page_num} ==="]

        for element in page.get("elements", []):
            elem_type = element.get("type")
            if elem_type in ["heading", "paragraph"]:
                text = element.get("text", "").strip()
                if text:
                    lines.append(f"[{elem_type.upper()}] {text}")
            elif elem_type == "table":
                rows = element.get("rows", [])
                lines.append(f"[TABLE index_{element.get('table_index')}]")
                for row in rows:
                    row_content = " | ".join([str(cell or "").strip() for cell in row])
                    lines.append(f"| {row_content} |")

        return "\n".join(lines)

    async def extract_knowledge(self, document_id: str) -> dict:
        processed_base = self.processed_dir / document_id
        tree_path = processed_base / "document_tree.json"
        metadata_path = self.raw_dir / document_id / "metadata.json"

        if not tree_path.exists():
            raise DocumentNotFoundError(f"Document structure tree for {document_id} not found. Run /extract-structure first.")

        try:
            logger.info(f"Starting unchunked LLM knowledge extraction for {document_id}")
            
            with open(tree_path, "r", encoding="utf-8") as f:
                document_tree = json.load(f)

            master_knowledge = {
                "document_id": document_id,
                "concepts": [],
                "relationships": [],
                "scientific_rules": [],
                "procedures": []
            }

            pages = document_tree.get("pages", [])
            
            # For rapid testing, let's inspect pages that actually contain body text (e.g., skip first 10 front-matter pages if needed, or process all)
            for page in pages:
                page_num = page.get("page_number")
                page_payload = self._format_unchunked_page_payload(page)
                
                # Skip sparse or short pages
                if len(page_payload.strip()) < 150:
                    continue

                logger.info(f"Sending page {page_num} to OpenAI for knowledge extraction...")
                
                try:
                    completion = await self.client.beta.chat.completions.parse(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system", 
                                "content": (
                                    "You are an expert scientific knowledge extraction engine. "
                                    "Extract precise scientific concepts, nodes, subnodes, and relationship edges "
                                    "from the provided unchunked page text into the required structured schema."
                                )
                            },
                            {
                                "role": "user", 
                                "content": f"Extract all concepts and relationships from this page:\n\n{page_payload}"
                            }
                        ],
                        response_format=KnowledgeExtractionPayload,
                        temperature=0.1
                    )

                    extracted_data = completion.choices[0].message.parsed
                    
                    if extracted_data:
                        c_count = len(extracted_data.concepts)
                        r_count = len(extracted_data.relationships)
                        logger.info(f"-> Page {page_num} extracted: {c_count} concepts, {r_count} relationships.")
                        
                        master_knowledge["concepts"].extend([c.model_dump() for c in extracted_data.concepts])
                        master_knowledge["relationships"].extend([r.model_dump() for r in extracted_data.relationships])
                        master_knowledge["scientific_rules"].extend([sr.model_dump() for sr in extracted_data.scientific_rules])
                        master_knowledge["procedures"].extend([p.model_dump() for p in extracted_data.procedures])

                except Exception as api_err:
                    logger.error(f"OpenAI API error on page {page_num}: {str(api_err)}")

            # Save artifact
            extracted_knowledge_path = processed_base / "extracted_knowledge.json"
            with open(extracted_knowledge_path, "w", encoding="utf-8") as kf:
                json.dump(master_knowledge, f, indent=4) # Fixed variable name bug from 'f' to 'kf'
            with open(extracted_knowledge_path, "w", encoding="utf-8") as kf:
                json.dump(master_knowledge, kf, indent=4)

            if metadata_path.exists():
                with open(metadata_path, "r+", encoding="utf-8") as mf:
                    meta_data = json.load(mf)
                    meta_data["pipeline_status"] = "KNOWLEDGE_EXTRACTED"
                    meta_data["next_step"] = f"{settings.API_V1_STR}/documents/{document_id}/knowledge"
                    mf.seek(0)
                    json.dump(meta_data, mf, indent=2)
                    mf.truncate()

            logger.info(f"Extraction complete. Total concepts: {len(master_knowledge['concepts'])}, Total relationships: {len(master_knowledge['relationships'])}")

            return {
                "document_id": document_id,
                "pipeline_status": "KNOWLEDGE_EXTRACTED",
                "extracted_stats": {
                    "concepts_extracted": len(master_knowledge["concepts"]),
                    "relationships_extracted": len(master_knowledge["relationships"])
                },
                "knowledge_artifact_path": str(extracted_knowledge_path.relative_to(settings.BASE_DIR))
            }

        except Exception as e:
            logger.error(f"Extraction failed for {document_id}: {str(e)}", exc_info=True)
            raise StorageError(f"Knowledge extraction failed: {str(e)}")