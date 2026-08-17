import json
import re
from pathlib import Path
from collections import Counter
from app.core.config import settings
from app.core.exceptions import DocumentNotFoundError, StorageError
from app.core.logger import logger

class GraphService:
    def __init__(self):
        self.raw_dir = settings.STORAGE_RAW_DIR
        self.processed_dir = settings.STORAGE_PROCESSED_DIR

    def _extract_keywords(self, text: str, top_n: int = 5) -> list[str]:
        """Simple keyword extraction heuristic based on term frequency (excluding common stopwords)."""
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", 
            "of", "with", "by", "from", "up", "about", "into", "through", "after", 
            "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", 
            "do", "does", "did", "this", "that", "these", "those", "it", "its", "as"
        }
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        filtered = [w for w in words if w not in stopwords]
        return [word for word, _ in Counter(filtered).most_common(top_n)]

    async def generate_knowledge_graph(self, document_id: str) -> dict:
        """Constructs a knowledge graph structure (nodes & edges) and writes graph.json."""
        processed_base = self.processed_dir / document_id
        knowledge_path = processed_base / "extracted_knowledge.json"
        metadata_path = self.raw_dir / document_id / "metadata.json"

        if not knowledge_path.exists():
            raise DocumentNotFoundError(f"Knowledge artifact for {document_id} not found. Run extract-knowledge step first.")

        try:
            logger.info(f"Generating knowledge graph for {document_id}")
            
            with open(knowledge_path, "r", encoding="utf-8") as kf:
                knowledge_data = json.load(kf)

            nodes = []
            edges = []

            # 1. Root Document Node
            doc_node_id = f"node_doc_{document_id}"
            nodes.append({
                "id": doc_node_id,
                "label": f"Document ({document_id})",
                "type": "DOCUMENT",
                "properties": {"document_id": document_id}
            })

            concept_nodes_map = {}

            # 2. Process Chunks into Nodes and Edges
            for chunk in knowledge_data.get("chunks", []):
                chunk_id = chunk["chunk_id"]
                page_num = chunk["page_number"]
                chunk_node_id = f"node_{chunk_id}"

                # Chunk Node
                nodes.append({
                    "id": chunk_node_id,
                    "label": f"Chunk P.{page_num}",
                    "type": "CHUNK",
                    "properties": {
                        "chunk_id": chunk_id,
                        "page_number": page_num,
                        "word_count": chunk["word_count"]
                    }
                })

                # Edge: Document -> Chunk
                edges.append({
                    "source": doc_node_id,
                    "target": chunk_node_id,
                    "relation": "CONTAINS"
                })

                # Extract and Link Concepts
                keywords = self._extract_keywords(chunk["content"], top_n=3)
                for kw in keywords:
                    concept_node_id = f"concept_{kw}"
                    if concept_node_id not in concept_nodes_map:
                        concept_nodes_map[concept_node_id] = {
                            "id": concept_node_id,
                            "label": kw.capitalize(),
                            "type": "CONCEPT",
                            "properties": {"term": kw}
                        }

                    # Edge: Chunk -> Concept
                    edges.append({
                        "source": chunk_node_id,
                        "target": concept_node_id,
                        "relation": "MENTIONS"
                    })

            # Append unique Concept Nodes
            nodes.extend(concept_nodes_map.values())

            graph_payload = {
                "document_id": document_id,
                "stats": {
                    "total_nodes": len(nodes),
                    "total_edges": len(edges),
                    "concept_count": len(concept_nodes_map)
                },
                "nodes": nodes,
                "edges": edges
            }

            graph_file_path = processed_base / "graph.json"
            with open(graph_file_path, "w", encoding="utf-8") as gf:
                json.dump(graph_payload, gf, indent=2)

            # Update status in metadata.json
            if metadata_path.exists():
                with open(metadata_path, "r+", encoding="utf-8") as mf:
                    meta_data = json.load(mf)
                    meta_data["pipeline_status"] = "GRAPH_GENERATED"
                    meta_data["next_step"] = f"{settings.API_V1_STR}/documents/{document_id}/graph"
                    mf.seek(0)
                    json.dump(meta_data, mf, indent=2)
                    mf.truncate()

            logger.info(f"Successfully generated graph.json for {document_id} with {len(nodes)} nodes")

            return {
                "document_id": document_id,
                "pipeline_status": "GRAPH_GENERATED",
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "graph_artifact_path": str(graph_file_path.relative_to(settings.BASE_DIR)),
                "next_step": f"{settings.API_V1_STR}/documents/{document_id}/graph"
            }

        except Exception as e:
            logger.error(f"Graph generation failed for {document_id}: {str(e)}")
            raise StorageError(f"Graph generation failed: {str(e)}")