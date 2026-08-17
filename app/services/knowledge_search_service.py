import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ProcessingError
from app.core.logger import logger


class KnowledgeSearchService:
    """
    Production-safe semantic knowledge search API.

    Correct position in Concept DB workflow:
        normalize-map
        -> validate-commit
        -> approve-proposals
        -> commit-approved-concepts
        -> sync-qdrant
        -> knowledge/search       <-- this service

    Architecture rule:
        MySQL Concept DB is source of truth.
        Qdrant is only a semantic candidate retriever.

    This service:
        1. Embeds user query.
        2. Searches Qdrant collection:
            concepts_3072 by default.
        3. Extracts concept_uid candidates from Qdrant payload.
        4. Loads canonical rows from MySQL:
            concepts
            concept_terms
            concept_fields
            concept_field_arrays
            concept_relationships
            relationship_types
            concept_types
        5. Returns MySQL-verified concepts with Qdrant score.
        6. Optionally writes an audit row into qe_pipeline_trace if table exists.

    Tables/columns matched to your current Concept DB:
        concepts:
            id, concept_uid, type_key, canonical_name, definition,
            type_data, status, has_vector

        concept_types:
            type_key, uid_prefix, label, group_key, depth_level,
            field_schema, vector_group

        concept_terms:
            concept_id, term, term_type, domain, confidence, source, status

        concept_fields:
            concept_id, type_key, field_key, val_string, val_number, val_bool
            Also supports older field_name/field_value shape dynamically.

        concept_field_arrays:
            concept_id, type_key, field_key, val_string, val_number
            Also supports older field_name shape dynamically.

        concept_relationships:
            source_concept_id, target_concept_id, relationship_type_id,
            status, confidence, strength, evidence

        relationship_types:
            id, type_key, label

        qe_pipeline_trace:
            optional audit table
    """

    DEFAULT_CONCEPTS_COLLECTION = "concepts_3072"
    DEFAULT_TERMS_COLLECTION = "concept_terms_unified_3072"
    DEFAULT_EMBEDDING_MODEL = "text-embedding-3-large"
    DEFAULT_EMBEDDING_DIMENSION = 3072

    SEARCHABLE_CONCEPT_STATUSES = {
        "approved",
        "active",
        "published",
        "trusted",
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self._table_columns: Dict[str, List[str]] = {}

    # ============================================================
    # BASIC HELPERS
    # ============================================================

    @staticmethod
    def _now_sql() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _now_iso() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S")

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def _parse_json_maybe(value: Any, default: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8", errors="ignore")
        if not isinstance(value, str):
            return default
        if not value.strip():
            return default
        try:
            return json.loads(value)
        except Exception:
            return default

    @staticmethod
    def _clean_url(value: Any) -> str:
        raw = str(value or "").strip().strip('"').strip("'")

        # Supports accidental markdown / Url(...) formatting.
        urls = re.findall(r"https?://[A-Za-z0-9.\-_:\/]+", raw)
        if urls:
            raw = urls[-1]

        if not raw:
            raw = "http://localhost:6333"

        if not raw.startswith(("http://", "https://")):
            raw = f"http://{raw}"

        return raw.rstrip("/")

    @staticmethod
    def _normalize_query(query: str) -> str:
        return re.sub(r"\s+", " ", str(query or "")).strip()

    def _qdrant_url(self) -> str:
        value = (
            getattr(settings, "QDRANT_URL", None)
            or os.getenv("QDRANT_URL")
            or f"http://{os.getenv('QDRANT_HOST', 'localhost')}:{os.getenv('QDRANT_PORT', '6333')}"
        )
        return self._clean_url(value)

    def _concepts_collection(self) -> str:
        return (
            getattr(settings, "QDRANT_CONCEPTS_COLLECTION", None)
            or os.getenv("QDRANT_CONCEPTS_COLLECTION")
            or self.DEFAULT_CONCEPTS_COLLECTION
        )

    def _terms_collection(self) -> str:
        return (
            getattr(settings, "QDRANT_TERMS_COLLECTION", None)
            or os.getenv("QDRANT_TERMS_COLLECTION")
            or self.DEFAULT_TERMS_COLLECTION
        )

    def _embedding_model(self) -> str:
        return (
            getattr(settings, "EMBEDDING_MODEL", None)
            or os.getenv("EMBEDDING_MODEL")
            or self.DEFAULT_EMBEDDING_MODEL
        )

    def _embedding_dimension(self) -> int:
        value = (
            getattr(settings, "EMBEDDING_DIMENSION", None)
            or os.getenv("EMBEDDING_DIMENSION")
            or self.DEFAULT_EMBEDDING_DIMENSION
        )
        try:
            return int(value)
        except Exception:
            return self.DEFAULT_EMBEDDING_DIMENSION

    def _openai_api_key(self) -> Optional[str]:
        return getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")

    # ============================================================
    # MYSQL HELPERS
    # ============================================================

    async def _mysql_preflight(self) -> None:
        try:
            result = await self.db.execute(text("SELECT 1 AS ok"))
            row = result.first()
            if not row or int(row[0]) != 1:
                raise RuntimeError("SELECT 1 failed")
        except Exception as exc:
            raise ProcessingError(
                f"MySQL is unavailable. knowledge search cannot continue. Database error: {exc}"
            ) from exc

    async def _columns(self, table_name: str) -> List[str]:
        if table_name in self._table_columns:
            return self._table_columns[table_name]

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

        cols = [str(row[0]) for row in result.all()]
        self._table_columns[table_name] = cols
        return cols

    async def _table_exists(self, table_name: str) -> bool:
        cols = await self._columns(table_name)
        return bool(cols)

    async def _require_table(self, table_name: str) -> List[str]:
        cols = await self._columns(table_name)
        if not cols:
            raise ProcessingError(f"Required MySQL table '{table_name}' does not exist.")
        return cols

    async def _require_schema(self) -> None:
        for table_name in [
            "concepts",
            "concept_types",
            "concept_terms",
        ]:
            await self._require_table(table_name)

    # ============================================================
    # EMBEDDINGS + QDRANT
    # ============================================================

    async def _embed_query(self, query: str) -> List[float]:
        api_key = self._openai_api_key()
        if not api_key:
            raise ProcessingError(
                "OPENAI_API_KEY is not configured. knowledge/search needs embeddings."
            )

        try:
            from openai import AsyncOpenAI
        except Exception as exc:
            raise ProcessingError(
                "openai package is not installed. Install it with: pip install openai"
            ) from exc

        client = AsyncOpenAI(api_key=api_key)
        response = await client.embeddings.create(
            model=self._embedding_model(),
            input=query,
        )

        vector = list(response.data[0].embedding)
        expected = self._embedding_dimension()

        if len(vector) != expected:
            raise ProcessingError(
                f"Embedding dimension mismatch. model={self._embedding_model()}, "
                f"expected={expected}, actual={len(vector)}."
            )

        return vector

    async def _httpx_client(self):
        try:
            import httpx
        except Exception as exc:
            raise ProcessingError(
                "httpx package is not installed. Install it with: pip install httpx"
            ) from exc

        return httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=60.0, write=60.0, pool=5.0)
        )

    async def _qdrant_search(
        self,
        collection: str,
        query_vector: List[float],
        top_k: int,
        min_score: Optional[float],
        type_keys: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        """
        Uses Qdrant REST.

        Qdrant 1.19 supports /points/query.
        Many installs still support /points/search.
        This method tries /points/query first, then falls back to /points/search.
        """

        qdrant_url = self._qdrant_url()

        qfilter = None
        if type_keys:
            qfilter = {
                "must": [
                    {
                        "key": "type_key",
                        "match": {"any": type_keys},
                    }
                ]
            }

        query_body = {
            "query": query_vector,
            "limit": top_k,
            "with_payload": True,
            "with_vector": False,
        }

        if qfilter:
            query_body["filter"] = qfilter

        if min_score is not None:
            query_body["score_threshold"] = min_score

        search_body = {
            "vector": query_vector,
            "limit": top_k,
            "with_payload": True,
            "with_vector": False,
        }

        if qfilter:
            search_body["filter"] = qfilter

        if min_score is not None:
            search_body["score_threshold"] = min_score

        async with await self._httpx_client() as client:
            # Preferred newer endpoint.
            query_response = await client.post(
                f"{qdrant_url}/collections/{collection}/points/query",
                json=query_body,
            )

            if query_response.status_code in {200, 201}:
                data = query_response.json()
                result = data.get("result", [])
                # Qdrant query result may be direct list or {points: []}
                if isinstance(result, dict) and isinstance(result.get("points"), list):
                    return result["points"]
                if isinstance(result, list):
                    return result

            # Fallback older endpoint.
            search_response = await client.post(
                f"{qdrant_url}/collections/{collection}/points/search",
                json=search_body,
            )

        if search_response.status_code not in {200, 201}:
            raise ProcessingError(
                f"Qdrant search failed. collection={collection}, "
                f"query_endpoint_status={query_response.status_code}, "
                f"query_endpoint_body={query_response.text}, "
                f"search_endpoint_status={search_response.status_code}, "
                f"search_endpoint_body={search_response.text}"
            )

        data = search_response.json()
        result = data.get("result", [])
        return result if isinstance(result, list) else []

    # ============================================================
    # MYSQL RESULT EXPANSION
    # ============================================================

    @staticmethod
    def _point_payload(point: Dict[str, Any]) -> Dict[str, Any]:
        payload = point.get("payload")
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _point_score(point: Dict[str, Any]) -> Optional[float]:
        value = point.get("score")
        if value is None:
            value = point.get("similarity")
        try:
            return float(value)
        except Exception:
            return None

    def _candidate_uids_from_points(self, points: List[Dict[str, Any]]) -> List[str]:
        uids: List[str] = []
        for point in points:
            payload = self._point_payload(point)
            uid = payload.get("concept_uid")
            if uid and str(uid) not in uids:
                uids.append(str(uid))
        return uids

    async def _load_concepts_by_uids(
        self,
        concept_uids: List[str],
        type_keys: Optional[List[str]],
        require_has_vector: bool,
    ) -> Dict[str, Dict[str, Any]]:
        if not concept_uids:
            return {}

        binds = {f"uid_{i}": uid for i, uid in enumerate(concept_uids)}
        placeholders = ", ".join(f":uid_{i}" for i in range(len(concept_uids)))

        type_clause = ""
        if type_keys:
            for i, type_key in enumerate(type_keys):
                binds[f"type_{i}"] = type_key
            type_placeholders = ", ".join(f":type_{i}" for i in range(len(type_keys)))
            type_clause = f"AND c.type_key IN ({type_placeholders})"

        has_vector_clause = "AND c.has_vector = 1" if require_has_vector else ""

        result = await self.db.execute(
            text(
                f"""
                SELECT
                    c.*,
                    ct.label AS type_label,
                    ct.group_key AS type_group_key,
                    ct.depth_level AS type_depth_level,
                    ct.vector_group AS vector_group
                FROM concepts c
                JOIN concept_types ct ON ct.type_key = c.type_key
                WHERE c.concept_uid IN ({placeholders})
                  AND c.status IN ('approved','active','published','trusted')
                  {type_clause}
                  {has_vector_clause}
                """
            ),
            binds,
        )

        rows = [dict(row) for row in result.mappings().all()]
        return {str(row["concept_uid"]): row for row in rows}

    async def _load_terms_for_concept_ids(self, concept_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
        if not concept_ids:
            return {}

        binds = {f"id_{i}": cid for i, cid in enumerate(concept_ids)}
        placeholders = ", ".join(f":id_{i}" for i in range(len(concept_ids)))

        result = await self.db.execute(
            text(
                f"""
                SELECT *
                FROM concept_terms
                WHERE concept_id IN ({placeholders})
                  AND status = 'active'
                ORDER BY
                    concept_id ASC,
                    CASE term_type
                        WHEN 'canonical' THEN 1
                        WHEN 'synonym' THEN 2
                        WHEN 'abbreviation' THEN 3
                        WHEN 'dataset_phrase' THEN 4
                        WHEN 'user_phrase' THEN 5
                        ELSE 6
                    END,
                    id ASC
                """
            ),
            binds,
        )

        grouped: Dict[int, List[Dict[str, Any]]] = {}
        for row in result.mappings().all():
            item = dict(row)
            grouped.setdefault(int(item["concept_id"]), []).append(item)

        return grouped

    async def _load_fields_for_concept_ids(self, concept_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
        if not concept_ids or not await self._table_exists("concept_fields"):
            return {}

        cols = await self._columns("concept_fields")

        # Your current Concept DB schema uses field_key.
        # Some older service versions used field_name.
        field_col = "field_key" if "field_key" in cols else "field_name" if "field_name" in cols else None

        binds = {f"id_{i}": cid for i, cid in enumerate(concept_ids)}
        placeholders = ", ".join(f":id_{i}" for i in range(len(concept_ids)))

        order_parts = ["concept_id ASC"]
        if field_col:
            order_parts.append(f"`{field_col}` ASC")
        if "id" in cols:
            order_parts.append("id ASC")

        order_sql = ", ".join(order_parts)

        result = await self.db.execute(
            text(
                f"""
                SELECT *
                FROM concept_fields
                WHERE concept_id IN ({placeholders})
                ORDER BY {order_sql}
                """
            ),
            binds,
        )

        grouped: Dict[int, List[Dict[str, Any]]] = {}
        for row in result.mappings().all():
            item = dict(row)
            grouped.setdefault(int(item["concept_id"]), []).append(item)

        return grouped

    async def _load_arrays_for_concept_ids(self, concept_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
        if not concept_ids or not await self._table_exists("concept_field_arrays"):
            return {}

        cols = await self._columns("concept_field_arrays")

        # Your current Concept DB schema uses field_key.
        # Some older service versions used field_name.
        field_col = "field_key" if "field_key" in cols else "field_name" if "field_name" in cols else None

        binds = {f"id_{i}": cid for i, cid in enumerate(concept_ids)}
        placeholders = ", ".join(f":id_{i}" for i in range(len(concept_ids)))

        order_parts = ["concept_id ASC"]
        if field_col:
            order_parts.append(f"`{field_col}` ASC")
        if "sort_order" in cols:
            order_parts.append("sort_order ASC")
        if "id" in cols:
            order_parts.append("id ASC")

        order_sql = ", ".join(order_parts)

        result = await self.db.execute(
            text(
                f"""
                SELECT *
                FROM concept_field_arrays
                WHERE concept_id IN ({placeholders})
                ORDER BY {order_sql}
                """
            ),
            binds,
        )

        grouped: Dict[int, List[Dict[str, Any]]] = {}
        for row in result.mappings().all():
            item = dict(row)
            grouped.setdefault(int(item["concept_id"]), []).append(item)

        return grouped

    async def _load_relationships_for_concept_ids(self, concept_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
        if not concept_ids or not await self._table_exists("concept_relationships"):
            return {}

        binds = {f"id_{i}": cid for i, cid in enumerate(concept_ids)}
        placeholders = ", ".join(f":id_{i}" for i in range(len(concept_ids)))

        has_relationship_types = await self._table_exists("relationship_types")

        if has_relationship_types:
            sql = f"""
                SELECT
                    cr.*,
                    rt.type_key AS relationship_type_key,
                    rt.label AS relationship_label,
                    src.concept_uid AS source_concept_uid,
                    src.canonical_name AS source_concept_name,
                    tgt.concept_uid AS target_concept_uid,
                    tgt.canonical_name AS target_concept_name
                FROM concept_relationships cr
                LEFT JOIN relationship_types rt ON rt.id = cr.relationship_type_id
                LEFT JOIN concepts src ON src.id = cr.source_concept_id
                LEFT JOIN concepts tgt ON tgt.id = cr.target_concept_id
                WHERE (cr.source_concept_id IN ({placeholders})
                       OR cr.target_concept_id IN ({placeholders}))
                  AND cr.status IN ('approved','active','trusted')
                ORDER BY cr.id ASC
            """
        else:
            sql = f"""
                SELECT cr.*
                FROM concept_relationships cr
                WHERE (cr.source_concept_id IN ({placeholders})
                       OR cr.target_concept_id IN ({placeholders}))
                  AND cr.status IN ('approved','active','trusted')
                ORDER BY cr.id ASC
            """

        result = await self.db.execute(text(sql), binds)

        grouped: Dict[int, List[Dict[str, Any]]] = {cid: [] for cid in concept_ids}
        concept_set = set(concept_ids)

        for row in result.mappings().all():
            item = dict(row)
            source_id = item.get("source_concept_id")
            target_id = item.get("target_concept_id")

            if source_id in concept_set:
                grouped.setdefault(int(source_id), []).append(item)
            if target_id in concept_set and target_id != source_id:
                grouped.setdefault(int(target_id), []).append(item)

        return grouped

    def _format_terms(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "term": row.get("term"),
                "term_type": row.get("term_type"),
                "domain": row.get("domain"),
                "confidence": float(row.get("confidence") or 1.0),
                "source": row.get("source"),
            }
            for row in rows
        ]

    def _format_fields(
        self,
        field_rows: List[Dict[str, Any]],
        array_rows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        fields: Dict[str, Any] = {}

        for row in field_rows:
            # Current schema uses field_key.
            # Older schema used field_name.
            name = row.get("field_key") or row.get("field_name")
            if not name:
                continue

            value = None

            # Current schema stores typed values.
            if row.get("val_string") is not None:
                value = row.get("val_string")
            elif row.get("val_number") is not None:
                value = row.get("val_number")
            elif row.get("val_bool") is not None:
                value = bool(row.get("val_bool"))
            elif row.get("field_value") is not None:
                value = row.get("field_value")
            elif row.get("value") is not None:
                value = row.get("value")

            fields[str(name)] = {
                "value": self._parse_json_maybe(value, value),
                "field_type": row.get("field_type"),
                "type_key": row.get("type_key"),
                "confidence": float(row.get("confidence") or 1.0),
                "source": row.get("source"),
            }

        arrays: Dict[str, List[Any]] = {}

        for row in array_rows:
            name = row.get("field_key") or row.get("field_name")
            if not name:
                continue

            value = None

            if row.get("val_string") is not None:
                value = row.get("val_string")
            elif row.get("val_number") is not None:
                value = row.get("val_number")
            elif row.get("value") is not None:
                value = row.get("value")

            arrays.setdefault(str(name), []).append(value)

        if arrays:
            fields["_arrays"] = arrays

        return fields

    def _format_relationships(self, rows: List[Dict[str, Any]], concept_id: int) -> List[Dict[str, Any]]:
        formatted = []

        for row in rows:
            source_id = row.get("source_concept_id")
            target_id = row.get("target_concept_id")

            direction = "outgoing" if source_id == concept_id else "incoming"

            formatted.append(
                {
                    "relationship_id": row.get("id"),
                    "direction": direction,
                    "relationship_type_id": row.get("relationship_type_id"),
                    "relationship_type_key": row.get("relationship_type_key"),
                    "relationship_label": row.get("relationship_label"),
                    "source_concept_uid": row.get("source_concept_uid"),
                    "source_concept_name": row.get("source_concept_name"),
                    "target_concept_uid": row.get("target_concept_uid"),
                    "target_concept_name": row.get("target_concept_name"),
                    "status": row.get("status"),
                    "confidence": float(row.get("confidence") or 1.0),
                    "strength": float(row.get("strength") or 1.0),
                    "evidence": self._parse_json_maybe(row.get("evidence"), row.get("evidence")),
                }
            )

        return formatted

    async def _mysql_lexical_fallback(
        self,
        query: str,
        top_k: int,
        type_keys: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        """
        Used only if Qdrant search returns zero candidates and fallback is enabled.
        It keeps API useful while still marking retrieval_mode=mysql_lexical_fallback.
        """

        binds: Dict[str, Any] = {
            "q_like": f"%{query}%",
            "top_k": top_k,
        }

        type_clause = ""
        if type_keys:
            for i, type_key in enumerate(type_keys):
                binds[f"type_{i}"] = type_key
            placeholders = ", ".join(f":type_{i}" for i in range(len(type_keys)))
            type_clause = f"AND c.type_key IN ({placeholders})"

        result = await self.db.execute(
            text(
                f"""
                SELECT DISTINCT
                    c.concept_uid,
                    0.0 AS score,
                    'mysql_lexical_fallback' AS retrieval_mode
                FROM concepts c
                LEFT JOIN concept_terms t ON t.concept_id = c.id AND t.status = 'active'
                WHERE c.status IN ('approved','active','published','trusted')
                  AND (
                        c.canonical_name LIKE :q_like
                        OR c.definition LIKE :q_like
                        OR t.term LIKE :q_like
                  )
                  {type_clause}
                ORDER BY c.updated_at DESC
                LIMIT :top_k
                """
            ),
            binds,
        )

        points = []
        for row in result.mappings().all():
            item = dict(row)
            points.append(
                {
                    "id": item.get("concept_uid"),
                    "score": item.get("score"),
                    "payload": {
                        "concept_uid": item.get("concept_uid"),
                        "retrieval_mode": item.get("retrieval_mode"),
                    },
                }
            )

        return points

    async def _expand_points_to_results(
        self,
        points: List[Dict[str, Any]],
        type_keys: Optional[List[str]],
        require_has_vector: bool,
        include_fields: bool,
        include_relationships: bool,
        include_qdrant_payload: bool,
    ) -> List[Dict[str, Any]]:
        candidate_uids = self._candidate_uids_from_points(points)
        concept_map = await self._load_concepts_by_uids(
            concept_uids=candidate_uids,
            type_keys=type_keys,
            require_has_vector=require_has_vector,
        )

        concept_ids = [
            int(row["id"])
            for row in concept_map.values()
            if row.get("id") is not None
        ]

        terms_by_id = await self._load_terms_for_concept_ids(concept_ids)

        fields_by_id: Dict[int, List[Dict[str, Any]]] = {}
        arrays_by_id: Dict[int, List[Dict[str, Any]]] = {}
        relationships_by_id: Dict[int, List[Dict[str, Any]]] = {}

        if include_fields:
            fields_by_id = await self._load_fields_for_concept_ids(concept_ids)
            arrays_by_id = await self._load_arrays_for_concept_ids(concept_ids)

        if include_relationships:
            relationships_by_id = await self._load_relationships_for_concept_ids(concept_ids)

        results: List[Dict[str, Any]] = []

        for rank, point in enumerate(points, start=1):
            payload = self._point_payload(point)
            uid = payload.get("concept_uid")

            if not uid or uid not in concept_map:
                continue

            concept = concept_map[uid]
            concept_id = int(concept["id"])

            item = {
                "rank": rank,
                "score": self._point_score(point),
                "concept": {
                    "id": concept.get("id"),
                    "concept_uid": concept.get("concept_uid"),
                    "type_key": concept.get("type_key"),
                    "type_label": concept.get("type_label"),
                    "type_group_key": concept.get("type_group_key"),
                    "vector_group": concept.get("vector_group"),
                    "canonical_name": concept.get("canonical_name"),
                    "definition": concept.get("definition"),
                    "status": concept.get("status"),
                    "has_vector": concept.get("has_vector"),
                    "type_data": self._parse_json_maybe(concept.get("type_data"), {}),
                },
                "terms": self._format_terms(terms_by_id.get(concept_id, [])),
            }

            if include_fields:
                item["fields"] = self._format_fields(
                    fields_by_id.get(concept_id, []),
                    arrays_by_id.get(concept_id, []),
                )

            if include_relationships:
                item["relationships"] = self._format_relationships(
                    relationships_by_id.get(concept_id, []),
                    concept_id=concept_id,
                )

            if include_qdrant_payload:
                item["qdrant_payload"] = payload
                item["qdrant_point_id"] = point.get("id")

            results.append(item)

        return results

    # ============================================================
    # AUDIT TRACE
    # ============================================================

    async def _write_trace_if_available(
        self,
        document_id: Optional[str],
        workspace_id: Optional[str],
        testing_id: Optional[str],
        query: str,
        response: Dict[str, Any],
    ) -> None:
        if not await self._table_exists("qe_pipeline_trace"):
            return

        cols = await self._columns("qe_pipeline_trace")

        payload_candidates = {
            "document_id": document_id,
            "workspace_id": workspace_id,
            "testing_id": testing_id,
            "stage": "knowledge_search",
            "pipeline_stage": "knowledge_search",
            "question": query,
            "query": query,
            "status": response.get("quality_gate_status") or response.get("status") or "COMPLETED",
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

        # Avoid failing search only because trace schema is different.
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
            logger.warning(f"knowledge/search trace insert skipped: {exc}")

    # ============================================================
    # QUALITY GATE
    # ============================================================

    def _quality_gate(self, qdrant_count: int, result_count: int, retrieval_mode: str) -> Dict[str, Any]:
        if result_count <= 0:
            return {
                "status": "NO_MATCHES_FOUND",
                "score": 70,
                "reason": "No MySQL-verified Concept DB matches were found.",
                "can_continue": True,
            }

        return {
            "status": "SEARCH_COMPLETED",
            "score": 100,
            "reason": (
                "Qdrant candidates were retrieved and verified against MySQL Concept DB."
                if retrieval_mode == "qdrant"
                else "Results were retrieved using MySQL lexical fallback."
            ),
            "can_continue": True,
            "qdrant_candidates": qdrant_count,
            "mysql_verified_results": result_count,
        }

    # ============================================================
    # MASTER
    # ============================================================

    async def search_knowledge(
        self,
        query: str,
        document_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        testing_id: Optional[str] = None,
        top_k: int = 10,
        min_score: Optional[float] = None,
        type_keys: Optional[List[str]] = None,
        collection: Optional[str] = None,
        include_fields: bool = True,
        include_relationships: bool = True,
        include_qdrant_payload: bool = False,
        require_has_vector: bool = True,
        fallback_to_mysql: bool = True,
    ) -> Dict[str, Any]:
        started = time.perf_counter()

        query = self._normalize_query(query)
        if not query:
            raise ProcessingError("query is required for knowledge/search.")

        top_k = max(1, min(int(top_k or 10), 50))
        collection = collection or self._concepts_collection()

        await self._mysql_preflight()
        await self._require_schema()

        retrieval_mode = "qdrant"

        query_vector = await self._embed_query(query)
        points = await self._qdrant_search(
            collection=collection,
            query_vector=query_vector,
            top_k=top_k,
            min_score=min_score,
            type_keys=type_keys,
        )

        qdrant_count = len(points)

        if not points and fallback_to_mysql:
            retrieval_mode = "mysql_lexical_fallback"
            points = await self._mysql_lexical_fallback(
                query=query,
                top_k=top_k,
                type_keys=type_keys,
            )

        results = await self._expand_points_to_results(
            points=points,
            type_keys=type_keys,
            require_has_vector=require_has_vector if retrieval_mode == "qdrant" else False,
            include_fields=include_fields,
            include_relationships=include_relationships,
            include_qdrant_payload=include_qdrant_payload,
        )

        elapsed = time.perf_counter() - started

        quality_gate = self._quality_gate(
            qdrant_count=qdrant_count,
            result_count=len(results),
            retrieval_mode=retrieval_mode,
        )

        response = {
            "status": quality_gate["status"],
            "query": query,
            "document_id": document_id,
            "workspace_id": workspace_id,
            "testing_id": testing_id,
            "retrieval_mode": retrieval_mode,
            "infrastructure": {
                "qdrant_url": self._qdrant_url(),
                "collection": collection,
                "embedding_model": self._embedding_model(),
                "embedding_dimension": self._embedding_dimension(),
                "mysql_source_of_truth": True,
            },
            "search_summary": {
                "top_k": top_k,
                "min_score": min_score,
                "type_keys": type_keys or [],
                "qdrant_candidates": qdrant_count,
                "mysql_verified_results": len(results),
                "include_fields": include_fields,
                "include_relationships": include_relationships,
            },
            "results": results,
            "quality_gate": quality_gate,
            "processing_time_seconds": round(elapsed, 2),
            "recommended_actions": [
                "Use concept_uid from results for exact concept detail lookup.",
                "Use type_keys filter to restrict search to sensory_attribute, descriptor, family, or sensory_scale.",
                "If qdrant_candidates is 0, verify concepts.has_vector=1 and QDRANT_CONCEPTS_COLLECTION.",
            ],
        }

        await self._write_trace_if_available(
            document_id=document_id,
            workspace_id=workspace_id,
            testing_id=testing_id,
            query=query,
            response=response,
        )

        await self.db.commit()

        logger.info(
            f"knowledge/search completed. query={query[:80]!r}, "
            f"retrieval_mode={retrieval_mode}, results={len(results)}, elapsed={elapsed:.2f}s"
        )

        return response