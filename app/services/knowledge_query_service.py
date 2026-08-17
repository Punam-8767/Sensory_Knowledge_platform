import json
import os
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ProcessingError
from app.core.logger import logger
from app.services.knowledge_search_service import KnowledgeSearchService


class KnowledgeQueryService:
    """
    Combined user-facing Knowledge Q&A API.

    This is the correct client-facing API for the Concept DB architecture.

    Public flow:
        User Question
            |
            v
        POST /api/v1/knowledge/query
            |
            v
        Final grounded answer + source concepts

    Internal architecture:
        User Question
            |
            v
        Embedding Model
            |
            v
        Qdrant
        Semantic Search only
            |
            v
        Candidate concept_uid values
            |
            v
        MySQL Concept DB
        Source of Truth
            |
            v
        Load canonical knowledge:
            - concepts
            - concept_types
            - concept_terms
            - concept_fields
            - concept_field_arrays
            - concept_relationships
            - relationship_types
            |
            v
        LLM grounded answer
            |
            v
        Return answer + canonical sources

    Important production rule:
        Qdrant is not the source of truth.
        LLM never answers directly from Qdrant payload.
        LLM answers only from MySQL-verified Concept DB context.

    This service depends on:
        KnowledgeSearchService

    Because search service already handles:
        - query embedding
        - Qdrant search
        - candidate concept_uid extraction
        - MySQL verification
        - dynamic concept_fields field_key / field_name support
        - dynamic concept_field_arrays field_key / field_name support
    """

    DEFAULT_ANSWER_MODEL = "gpt-4o-mini"

    def __init__(self, db: AsyncSession):
        self.db = db
        self.search_service = KnowledgeSearchService(db=db)

    # ============================================================
    # BASIC HELPERS
    # ============================================================

    @staticmethod
    def _now_sql() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def _safe_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, default=str)
        return str(value)

    def _openai_api_key(self) -> Optional[str]:
        return getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")

    def _answer_model(self) -> str:
        return (
            getattr(settings, "ANSWER_MODEL", None)
            or os.getenv("ANSWER_MODEL")
            or getattr(settings, "OPENAI_CHAT_MODEL", None)
            or os.getenv("OPENAI_CHAT_MODEL")
            or self.DEFAULT_ANSWER_MODEL
        )

    # ============================================================
    # CONTEXT BUILDING
    # ============================================================

    def _build_context_from_verified_results(
        self,
        verified_results: List[Dict[str, Any]],
        max_concepts: int,
    ) -> str:
        """
        Builds grounded LLM context from MySQL-verified search results.

        The input comes from KnowledgeSearchService, so every concept was:
            Qdrant candidate -> concept_uid -> MySQL canonical verification
        """

        chunks: List[str] = []

        for index, item in enumerate(verified_results[:max_concepts], start=1):
            concept = item.get("concept") or {}
            terms = item.get("terms") or []
            fields = item.get("fields") or {}
            relationships = item.get("relationships") or []

            concept_uid = concept.get("concept_uid")
            type_key = concept.get("type_key")
            type_label = concept.get("type_label")
            canonical_name = concept.get("canonical_name")
            definition = concept.get("definition")
            status = concept.get("status")
            score = item.get("score")
            type_data = concept.get("type_data") or {}

            term_lines: List[str] = []
            for term in terms:
                term_value = term.get("term")
                term_type = term.get("term_type")
                domain = term.get("domain")
                if term_value:
                    line = str(term_value)
                    if term_type:
                        line += f" [{term_type}]"
                    if domain:
                        line += f" domain={domain}"
                    term_lines.append(line)

            field_lines: List[str] = []
            if isinstance(fields, dict):
                for field_key, field_payload in fields.items():
                    if field_key == "_arrays":
                        continue

                    if isinstance(field_payload, dict):
                        value = field_payload.get("value")
                    else:
                        value = field_payload

                    field_lines.append(f"{field_key}: {self._safe_text(value)}")

            relationship_lines: List[str] = []
            for rel in relationships:
                rel_type = rel.get("relationship_type_key") or rel.get("relationship_label")
                source_uid = rel.get("source_concept_uid")
                source_name = rel.get("source_concept_name")
                target_uid = rel.get("target_concept_uid")
                target_name = rel.get("target_concept_name")

                if rel_type:
                    relationship_lines.append(
                        f"{source_uid} ({source_name}) --{rel_type}--> {target_uid} ({target_name})"
                    )

            chunk_parts = [
                f"[Verified Concept {index}]",
                f"rank: {item.get('rank')}",
                f"score: {score}",
                f"concept_uid: {concept_uid}",
                f"type_key: {type_key}",
                f"type_label: {type_label}",
                f"canonical_name: {canonical_name}",
                f"status: {status}",
            ]

            if definition:
                chunk_parts.append(f"definition: {definition}")

            if type_data:
                chunk_parts.append(
                    "type_data: " + json.dumps(type_data, ensure_ascii=False, default=str)
                )

            if term_lines:
                chunk_parts.append("terms:\n- " + "\n- ".join(term_lines[:20]))

            if field_lines:
                chunk_parts.append("fields:\n- " + "\n- ".join(field_lines[:30]))

            if relationship_lines:
                chunk_parts.append("relationships:\n- " + "\n- ".join(relationship_lines[:30]))

            chunks.append("\n".join(chunk_parts))

        return "\n\n".join(chunks)

    def _source_concepts(self, verified_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        sources: List[Dict[str, Any]] = []

        for item in verified_results:
            concept = item.get("concept") or {}
            sources.append(
                {
                    "rank": item.get("rank"),
                    "score": item.get("score"),
                    "concept_uid": concept.get("concept_uid"),
                    "type_key": concept.get("type_key"),
                    "canonical_name": concept.get("canonical_name"),
                    "definition": concept.get("definition"),
                    "status": concept.get("status"),
                    "has_vector": concept.get("has_vector"),
                }
            )

        return sources

    # ============================================================
    # ANSWER GENERATION
    # ============================================================

    def _style_instruction(self, answer_style: str) -> str:
        answer_style = str(answer_style or "short").lower().strip()

        if answer_style == "technical":
            return (
                "Answer for an internal technical user. "
                "Mention concept_uid, type_key, and important relationships when useful."
            )

        if answer_style == "client":
            return (
                "Answer in simple client-friendly language. "
                "Avoid heavy technical words unless needed."
            )

        if answer_style == "detailed":
            return (
                "Give a clear detailed answer. "
                "Use only the verified context and keep it practical."
            )

        return "Answer in 3 to 6 short bullet points."

    async def _generate_grounded_answer(
        self,
        question: str,
        context: str,
        answer_style: str,
    ) -> str:
        api_key = self._openai_api_key()
        if not api_key:
            raise ProcessingError(
                "OPENAI_API_KEY is not configured. knowledge/query needs chat completion."
            )

        try:
            from openai import AsyncOpenAI
        except Exception as exc:
            raise ProcessingError(
                "openai package is not installed. Install it with: pip install openai"
            ) from exc

        system_prompt = f"""
You are answering from a Sensory Concept DB.

Strict rules:
- Use only the provided MySQL-verified canonical Concept DB context.
- Do not invent facts.
- Do not answer from general knowledge.
- If the context is not enough, say: "I could not find enough approved Concept DB knowledge to answer this fully."
- Mention source concept_uid values at the end.
- Keep the answer practical and easy to understand.
- {self._style_instruction(answer_style)}
""".strip()

        user_prompt = f"""
User question:
{question}

MySQL-verified canonical Concept DB context:
{context}

Write the final answer.
""".strip()

        client = AsyncOpenAI(api_key=api_key)

        response = await client.chat.completions.create(
            model=self._answer_model(),
            temperature=0.1,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        answer = response.choices[0].message.content or ""
        return answer.strip()

    # ============================================================
    # OPTIONAL TRACE
    # ============================================================

    async def _columns(self, table_name: str) -> List[str]:
        result = await self.db.execute(
            text(
                """
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = :table_name
                ORDER BY ORDINAL_POSITION
                """
            ),
            {"table_name": table_name},
        )
        return [str(row[0]) for row in result.all()]

    async def _write_trace_if_available(
        self,
        document_id: Optional[str],
        workspace_id: Optional[str],
        testing_id: Optional[str],
        question: str,
        response: Dict[str, Any],
    ) -> None:
        cols = await self._columns("qe_pipeline_trace")
        if not cols:
            return

        payload_candidates = {
            "document_id": document_id,
            "workspace_id": workspace_id,
            "testing_id": testing_id,
            "stage": "knowledge_query",
            "pipeline_stage": "knowledge_query",
            "question": question,
            "query": question,
            "status": response.get("status"),
            "result_json": self._json(response),
            "response_json": self._json(response),
            "payload": self._json(response),
            "created_at": self._now_sql(),
            "updated_at": self._now_sql(),
        }

        filtered = {
            key: value
            for key, value in payload_candidates.items()
            if key in cols
        }

        if not filtered:
            return

        try:
            col_sql = ", ".join(f"`{col}`" for col in filtered.keys())
            val_sql = ", ".join(f":{col}" for col in filtered.keys())

            await self.db.execute(
                text(f"INSERT INTO qe_pipeline_trace ({col_sql}) VALUES ({val_sql})"),
                filtered,
            )
        except Exception as exc:
            logger.warning(f"knowledge/query trace insert skipped: {exc}")

    # ============================================================
    # MASTER
    # ============================================================

    async def query_knowledge(
        self,
        question: str,
        document_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        testing_id: Optional[str] = None,
        top_k: int = 5,
        min_score: Optional[float] = None,
        type_keys: Optional[List[str]] = None,
        collection: Optional[str] = None,
        answer_style: str = "short",
        include_canonical_knowledge: bool = True,
        include_search_debug: bool = False,
        fallback_to_mysql: bool = True,
    ) -> Dict[str, Any]:
        started = time.perf_counter()

        question = str(question or "").strip()
        if not question:
            raise ProcessingError("question is required for knowledge/query.")

        top_k = max(1, min(int(top_k or 5), 20))

        # Step 1:
        # Search Qdrant + verify candidates against MySQL Concept DB.
        search_result = await self.search_service.search_knowledge(
            query=question,
            document_id=document_id,
            workspace_id=workspace_id,
            testing_id=testing_id,
            top_k=top_k,
            min_score=min_score,
            type_keys=type_keys,
            collection=collection,
            include_fields=True,
            include_relationships=True,
            include_qdrant_payload=False,
            require_has_vector=True,
            fallback_to_mysql=fallback_to_mysql,
        )

        verified_results = search_result.get("results") or []

        # Step 2:
        # If no verified canonical knowledge, do not let LLM invent.
        if not verified_results:
            answer = "I could not find enough approved Concept DB knowledge to answer this fully."
            status_value = "NO_GROUNDED_ANSWER"
            quality_gate = {
                "status": status_value,
                "score": 70,
                "reason": "No MySQL-verified Concept DB context was available for answer generation.",
                "can_continue": True,
            }
        else:
            grounded_context = self._build_context_from_verified_results(
                verified_results=verified_results,
                max_concepts=top_k,
            )

            answer = await self._generate_grounded_answer(
                question=question,
                context=grounded_context,
                answer_style=answer_style,
            )

            status_value = "ANSWER_COMPLETED"
            quality_gate = {
                "status": status_value,
                "score": 100,
                "reason": (
                    "Answer was generated from Qdrant-retrieved and MySQL-verified "
                    "canonical Concept DB context."
                ),
                "can_continue": True,
            }

        elapsed = time.perf_counter() - started

        response = {
            "status": status_value,
            "question": question,
            "answer": answer,
            "document_id": document_id,
            "workspace_id": workspace_id,
            "testing_id": testing_id,
            "answer_style": answer_style,
            "architecture": {
                "mysql_source_of_truth": True,
                "qdrant_semantic_retriever": True,
                "llm_grounded_on_mysql_verified_context": True,
                "flow": [
                    "user_question",
                    "embedding_model",
                    "qdrant_semantic_search",
                    "candidate_concept_uids",
                    "mysql_concept_db_verification",
                    "canonical_context_loading",
                    "grounded_answer_generation",
                ],
            },
            "retrieval": {
                "mode": search_result.get("retrieval_mode"),
                "summary": search_result.get("search_summary", {}),
                "infrastructure": search_result.get("infrastructure", {}),
            },
            "source_concepts": self._source_concepts(verified_results),
            "quality_gate": quality_gate,
            "processing_time_seconds": round(elapsed, 2),
        }

        if include_canonical_knowledge:
            response["canonical_knowledge"] = verified_results

        if include_search_debug:
            response["search_debug"] = search_result

        await self._write_trace_if_available(
            document_id=document_id,
            workspace_id=workspace_id,
            testing_id=testing_id,
            question=question,
            response=response,
        )

        await self.db.commit()

        logger.info(
            f"knowledge/query completed. status={status_value}, "
            f"sources={len(verified_results)}, elapsed={elapsed:.2f}s"
        )

        return response