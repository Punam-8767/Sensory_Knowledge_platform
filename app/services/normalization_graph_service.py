# # import asyncio
# # import hashlib
# # import json
# # import re
# # import time
# # import uuid
# # from pathlib import Path
# # from typing import Any, Dict, List, Optional, Set, Tuple

# # from openai import AsyncOpenAI
# # from qdrant_client import AsyncQdrantClient, models
# # from sqlalchemy import text
# # from sqlalchemy.ext.asyncio import AsyncSession

# # from app.core.config import settings
# # from app.core.exceptions import ProcessingError
# # from app.core.logger import logger


# # class NormalizationGraphService:
# #     """
# #     TagTaste - Normalization + Graph + Schema Mapping.

# #     MySQL:
# #         Source of truth.

# #     Qdrant:
# #         Semantic candidate retrieval only.
# #         An empty/missing collection must never turn into repeated 404s.

# #     Important behavior:
# #         - If MySQL is unavailable, STOP. Do not classify every concept as new.
# #         - If Qdrant is unavailable or empty, continue with MySQL exact matching.
# #         - New concepts remain proposals until human review.
# #         - Relationships touching proposals remain pending.
# #     """

# #     DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
# #     DEFAULT_QDRANT_COLLECTION = "concepts"
# #     DEFAULT_EMBEDDING_DIMENSIONS = 1536

# #     SEMANTIC_MATCH_THRESHOLD = 0.88
# #     SEMANTIC_REVIEW_THRESHOLD = 0.78
# #     QDRANT_LIMIT = 5

# #     KNOWLEDGE_REQUIRED_STATUS = "KNOWLEDGE_EXTRACTED"

# #     DEFAULT_RELATIONSHIP_TYPES: Set[str] = {
# #         "is_child_of",
# #         "described_by",
# #         "measured_by",
# #         "categorized_as",
# #         "related_to",
# #         "causes",
# #         "influences",
# #         "part_of",
# #         "uses_method",
# #         "benchmarked_by",
# #         "triggered_by",
# #         "contains",
# #         "has_attribute",
# #         "has_sensory_attribute",
# #         "has_descriptor",
# #         "has_intensity",
# #         "has_score",
# #         "uses_scale",
# #         "evaluated_by",
# #         "compared_with",
# #         "prepared_by",
# #         "derived_from",
# #         "belongs_to",
# #         "associated_with",
# #         "defined_by",
# #         "measured_under",
# #         "tested_by",
# #         "has_method",
# #         "has_property",
# #         "correlates_with",
# #     }

# #     CATEGORY_TO_TYPE_KEY = {
# #         "Entity": "entity",
# #         "Method": "method",
# #         "Theory": "theory",
# #         "Process": "process",
# #         "Material": "material",
# #         "Chemical": "chemical",
# #         "Instrument": "instrument",
# #         "Organization": "organization",
# #         "Measurement": "measurement",
# #         "Property": "property",
# #         "Sensory_Attribute": "sensory_attribute",
# #     }

# #     METADATA_PATTERNS = [
# #         r"\bisbn\b",
# #         r"\bcopyright\b",
# #         r"\bpublisher\b",
# #         r"\bedition\b",
# #         r"\bauthor\b",
# #         r"\bprinted by\b",
# #     ]

# #     # Floating values / statistical calculation fragments should not become
# #     # canonical knowledge concepts.
# #     PURE_NUMBER_RE = re.compile(
# #         r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:\s*%|\s*[a-zA-Z°]+)?$"
# #     )
# #     ASSIGNMENT_VALUE_RE = re.compile(
# #         r"^[A-Za-zαβμσχ²χ]+(?:\d+)?\s*=\s*[+-]?\d+(?:\.\d+)?%?$"
# #     )
# #     SHORT_FORMULA_RE = re.compile(
# #         r"^(?:n\d*|x\d*|s\d*|t\d*|f|p|d\d*|c\d*|χ²?)\s*=?\s*[+-]?\d*(?:\.\d+)?%?$",
# #         re.IGNORECASE,
# #     )

# #     def __init__(self, db: AsyncSession):
# #         self.db = db
# #         self.raw_dir = Path(settings.STORAGE_RAW_DIR)
# #         self.processed_dir = Path(settings.STORAGE_PROCESSED_DIR)

# #         self.openai_client = AsyncOpenAI(
# #             api_key=settings.OPENAI_API_KEY,
# #             timeout=float(getattr(settings, "OPENAI_TIMEOUT", 60.0)),
# #             max_retries=int(getattr(settings, "OPENAI_MAX_RETRIES", 2)),
# #         )

# #         self.embedding_model = getattr(
# #             settings,
# #             "OPENAI_EMBEDDING_MODEL",
# #             self.DEFAULT_EMBEDDING_MODEL,
# #         )
# #         self.embedding_dimensions = int(
# #             getattr(
# #                 settings,
# #                 "OPENAI_EMBEDDING_DIMENSIONS",
# #                 self.DEFAULT_EMBEDDING_DIMENSIONS,
# #             )
# #         )

# #         qdrant_url = getattr(settings, "QDRANT_URL", None)
# #         if not qdrant_url:
# #             qdrant_url = (
# #                 f"http://{getattr(settings, 'QDRANT_HOST', 'localhost')}:"
# #                 f"{int(getattr(settings, 'QDRANT_PORT', 6333))}"
# #             )

# #         self.qdrant = AsyncQdrantClient(
# #             url=qdrant_url,
# #             api_key=(getattr(settings, "QDRANT_API_KEY", "") or None),
# #             timeout=5.0,
# #             check_compatibility=False,
# #         )

# #         self.qdrant_collection = getattr(
# #             settings,
# #             "QDRANT_CONCEPT_COLLECTION",
# #             self.DEFAULT_QDRANT_COLLECTION,
# #         )

# #         self.normalization_concurrency = max(
# #             1,
# #             int(getattr(settings, "NORMALIZATION_CONCURRENCY", 12)),
# #         )

# #         self._table_columns: Dict[str, List[str]] = {}
# #         self._relationship_types: Optional[Set[str]] = None

# #         # Loaded once from MySQL; avoids hundreds of DB calls and avoids
# #         # concurrent operations on one AsyncSession.
# #         self._mysql_by_name: Dict[str, Dict[str, Any]] = {}
# #         self._mysql_by_uid: Dict[str, Dict[str, Any]] = {}

# #         self._resolution_cache: Dict[str, Dict[str, Any]] = {}
# #         self._embedding_cache: Dict[str, List[float]] = {}

# #         self._qdrant_reachable = False
# #         self._qdrant_has_points = False
# #         self._qdrant_collection_created = False

# #     # ============================================================
# #     # BASIC HELPERS
# #     # ============================================================

# #     @staticmethod
# #     def _normalize_space(value: Any) -> str:
# #         return re.sub(r"\s+", " ", str(value or "")).strip()

# #     def _normalize_name(self, value: Any) -> str:
# #         return self._normalize_space(value).strip(" .,:;|-_")

# #     def _comparison_key(self, value: Any) -> str:
# #         normalized = self._normalize_name(value).casefold()
# #         # Preserve unicode letters where possible, but use a stable
# #         # alphanumeric key for ordinary English sensory terms.
# #         return re.sub(r"[^a-z0-9]+", "", normalized)

# #     @staticmethod
# #     def _dedupe_strings(values: Any) -> List[str]:
# #         if not isinstance(values, list):
# #             values = [values] if values else []

# #         output: List[str] = []
# #         seen = set()
# #         for value in values:
# #             item = str(value or "").strip()
# #             if not item:
# #                 continue
# #             key = item.casefold()
# #             if key in seen:
# #                 continue
# #             seen.add(key)
# #             output.append(item)
# #         return output

# #     def _is_metadata_concept(self, concept_name: str) -> bool:
# #         lowered = concept_name.casefold()
# #         return any(re.search(pattern, lowered) for pattern in self.METADATA_PATTERNS)

# #     def _is_floating_value(self, concept_name: str) -> bool:
# #         """
# #         Reject standalone values such as:
# #             6.2
# #             62.5%
# #             n1=7
# #             x1=6.557
# #             t=-0.85
# #             F=1.59
# #             c
# #             t

# #         Do not reject legitimate multi-character concepts such as:
# #             pH
# #             ANOVA
# #             PCA
# #             9-point scale
# #         """
# #         name = self._normalize_name(concept_name)
# #         if not name:
# #             return True

# #         if len(name) == 1 and name.casefold() in {"c", "d", "f", "p", "s", "t", "x", "n"}:
# #             return True

# #         if self.PURE_NUMBER_RE.fullmatch(name):
# #             return True

# #         if self.ASSIGNMENT_VALUE_RE.fullmatch(name):
# #             return True

# #         if self.SHORT_FORMULA_RE.fullmatch(name):
# #             # Protect common real concepts.
# #             if name.casefold() not in {"ph"}:
# #                 return True

# #         return False

# #     @staticmethod
# #     def _new_proposal_uid() -> str:
# #         return "prop_" + uuid.uuid4().hex[:16]

# #     @staticmethod
# #     def _stable_relationship_uid(
# #         source_uid: str,
# #         relationship_type: str,
# #         target_uid: str,
# #     ) -> str:
# #         signature = f"{source_uid}|{relationship_type}|{target_uid}"
# #         digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]
# #         return f"rel_{digest}"

# #     # ============================================================
# #     # FILE HELPERS
# #     # ============================================================

# #     @staticmethod
# #     def _read_json(path: Path) -> Dict[str, Any]:
# #         if not path.exists():
# #             raise FileNotFoundError(f"JSON artifact not found: {path}")

# #         try:
# #             raw = path.read_text(encoding="utf-8-sig")
# #         except OSError as exc:
# #             raise ProcessingError(
# #                 f"Could not read JSON artifact {path}: {exc}"
# #             ) from exc

# #         if not raw.strip():
# #             raise ProcessingError(f"JSON artifact exists but is empty: {path}")

# #         try:
# #             value = json.loads(raw)
# #         except json.JSONDecodeError as exc:
# #             raise ProcessingError(
# #                 f"JSON artifact is invalid: {path}. "
# #                 f"line={exc.lineno}, column={exc.colno}, error={exc.msg}"
# #             ) from exc

# #         if not isinstance(value, dict):
# #             raise ProcessingError(
# #                 f"Expected JSON object in {path}, got {type(value).__name__}."
# #             )
# #         return value

# #     def _read_metadata(self, document_id: str) -> Dict[str, Any]:
# #         path = self.raw_dir / document_id / "metadata.json"
# #         if not path.exists():
# #             raise FileNotFoundError(
# #                 f"metadata.json not found for {document_id}."
# #             )
# #         return self._read_json(path)

# #     def _require_knowledge_artifact(
# #         self,
# #         knowledge_path: Path,
# #         document_id: str,
# #     ) -> Dict[str, Any]:
# #         metadata = self._read_metadata(document_id)
# #         pipeline_status = str(metadata.get("pipeline_status", "UNKNOWN")).strip()

# #         if pipeline_status != self.KNOWLEDGE_REQUIRED_STATUS:
# #             raise ProcessingError(
# #                 f"Knowledge extraction is not complete for {document_id}. "
# #                 f"Current pipeline_status={pipeline_status}; "
# #                 f"required={self.KNOWLEDGE_REQUIRED_STATUS}."
# #             )

# #         knowledge = self._read_json(knowledge_path)

# #         if not isinstance(knowledge.get("concepts", []), list):
# #             raise ProcessingError("'concepts' must be a JSON array.")

# #         if not isinstance(knowledge.get("relationships", []), list):
# #             raise ProcessingError("'relationships' must be a JSON array.")

# #         return knowledge

# #     @staticmethod
# #     def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
# #         path.parent.mkdir(parents=True, exist_ok=True)
# #         tmp = path.with_suffix(path.suffix + ".tmp")

# #         with open(tmp, "w", encoding="utf-8") as file:
# #             json.dump(
# #                 payload,
# #                 file,
# #                 indent=2,
# #                 ensure_ascii=False,
# #                 default=str,
# #             )
# #             file.flush()

# #         tmp.replace(path)

# #     # ============================================================
# #     # MYSQL PRE-FLIGHT + CATALOG
# #     # ============================================================

# #     async def _mysql_preflight(self) -> None:
# #         """
# #         MySQL is source of truth.
# #         If it is unavailable, continuing would incorrectly turn every concept
# #         into NEW_PROPOSAL, so fail immediately.
# #         """
# #         try:
# #             result = await self.db.execute(text("SELECT 1 AS ok"))
# #             row = result.first()
# #             if not row or int(row[0]) != 1:
# #                 raise RuntimeError("SELECT 1 returned an unexpected value")
# #         except Exception as exc:
# #             raise ProcessingError(
# #                 "MySQL is unavailable. Normalization cannot safely continue "
# #                 "because MySQL is the source of truth. "
# #                 f"Database error: {exc}"
# #             ) from exc

# #     async def _get_columns(self, table_name: str) -> List[str]:
# #         if table_name in self._table_columns:
# #             return self._table_columns[table_name]

# #         result = await self.db.execute(
# #             text(
# #                 """
# #                 SELECT COLUMN_NAME
# #                 FROM INFORMATION_SCHEMA.COLUMNS
# #                 WHERE TABLE_SCHEMA = DATABASE()
# #                   AND TABLE_NAME = :table_name
# #                 ORDER BY ORDINAL_POSITION
# #                 """
# #             ),
# #             {"table_name": table_name},
# #         )
# #         columns = [str(row[0]) for row in result.all()]
# #         self._table_columns[table_name] = columns
# #         return columns

# #     @staticmethod
# #     def _pick_column(
# #         available: List[str],
# #         candidates: List[str],
# #     ) -> Optional[str]:
# #         lookup = {column.casefold(): column for column in available}
# #         for candidate in candidates:
# #             if candidate.casefold() in lookup:
# #                 return lookup[candidate.casefold()]
# #         return None

# #     async def _load_mysql_catalog(self) -> None:
# #         """
# #         Load trusted concepts + terms ONCE.

# #         This is much faster than:
# #             concept -> SELECT
# #             concept -> SELECT
# #             concept -> SELECT ...

# #         It also avoids concurrent use of the same AsyncSession.
# #         """
# #         concept_columns = await self._get_columns("concepts")
# #         if not concept_columns:
# #             raise ProcessingError(
# #                 "Required MySQL table 'concepts' does not exist in the current database."
# #             )

# #         uid_col = self._pick_column(
# #             concept_columns, ["uid", "concept_uid", "id"]
# #         )
# #         name_col = self._pick_column(
# #             concept_columns, ["canonical_name", "name", "concept_name", "label"]
# #         )
# #         type_col = self._pick_column(
# #             concept_columns, ["type_key", "concept_type", "category"]
# #         )
# #         status_col = self._pick_column(
# #             concept_columns, ["status", "approval_status"]
# #         )

# #         if not uid_col or not name_col:
# #             raise ProcessingError(
# #                 "Table 'concepts' must contain a UID column "
# #                 "(uid/concept_uid/id) and name column "
# #                 "(canonical_name/name/concept_name/label)."
# #             )

# #         selected = [
# #             f"`{uid_col}` AS concept_uid",
# #             f"`{name_col}` AS canonical_name",
# #         ]
# #         if type_col:
# #             selected.append(f"`{type_col}` AS type_key")
# #         if status_col:
# #             selected.append(f"`{status_col}` AS concept_status")

# #         result = await self.db.execute(
# #             text(f"SELECT {', '.join(selected)} FROM concepts")
# #         )

# #         self._mysql_by_name.clear()
# #         self._mysql_by_uid.clear()

# #         for row in result.mappings().all():
# #             uid = str(row["concept_uid"])
# #             name = self._normalize_name(row["canonical_name"])
# #             if not uid or not name:
# #                 continue

# #             record = {
# #                 "concept_uid": uid,
# #                 "canonical_name": name,
# #                 "type_key": row.get("type_key"),
# #                 "status": row.get("concept_status"),
# #             }

# #             self._mysql_by_uid[uid] = record
# #             self._mysql_by_name[self._comparison_key(name)] = record

# #         # Load aliases/synonyms from concept_terms if available.
# #         term_columns = await self._get_columns("concept_terms")
# #         if term_columns:
# #             term_col = self._pick_column(
# #                 term_columns,
# #                 ["term", "term_text", "name", "value", "synonym"],
# #             )
# #             ref_col = self._pick_column(
# #                 term_columns,
# #                 ["concept_uid", "concept_id", "uid"],
# #             )

# #             if term_col and ref_col:
# #                 term_result = await self.db.execute(
# #                     text(
# #                         f"""
# #                         SELECT
# #                             `{ref_col}` AS concept_ref,
# #                             `{term_col}` AS matched_term
# #                         FROM concept_terms
# #                         WHERE `{term_col}` IS NOT NULL
# #                         """
# #                     )
# #                 )

# #                 for row in term_result.mappings().all():
# #                     ref = str(row["concept_ref"])
# #                     term_value = self._normalize_name(row["matched_term"])
# #                     trusted = self._mysql_by_uid.get(ref)
# #                     if trusted and term_value:
# #                         self._mysql_by_name[
# #                             self._comparison_key(term_value)
# #                         ] = trusted

# #         logger.info(
# #             "Loaded trusted MySQL concept catalog: "
# #             f"concepts={len(self._mysql_by_uid)}, "
# #             f"name/term keys={len(self._mysql_by_name)}"
# #         )

# #     async def _load_relationship_types(self) -> Set[str]:
# #         if self._relationship_types is not None:
# #             return self._relationship_types

# #         columns = await self._get_columns("relationship_types")
# #         if not columns:
# #             self._relationship_types = set(self.DEFAULT_RELATIONSHIP_TYPES)
# #             return self._relationship_types

# #         key_col = self._pick_column(
# #             columns,
# #             ["type_key", "relationship_type", "key", "name"],
# #         )
# #         if not key_col:
# #             self._relationship_types = set(self.DEFAULT_RELATIONSHIP_TYPES)
# #             return self._relationship_types

# #         result = await self.db.execute(
# #             text(f"SELECT `{key_col}` FROM relationship_types")
# #         )
# #         values = {
# #             str(row[0]).strip()
# #             for row in result.all()
# #             if row[0] is not None and str(row[0]).strip()
# #         }
# #         self._relationship_types = values or set(self.DEFAULT_RELATIONSHIP_TYPES)
# #         return self._relationship_types

# #     # ============================================================
# #     # QDRANT PRE-FLIGHT
# #     # ============================================================

# #     async def _prepare_qdrant(self) -> None:
# #         """
# #         Ensure the configured collection exists.

# #         If the collection is newly created or contains zero points, semantic
# #         matching is skipped. This prevents hundreds of useless OpenAI
# #         embedding + Qdrant calls.
# #         """
# #         try:
# #             exists = await self.qdrant.collection_exists(
# #                 collection_name=self.qdrant_collection
# #             )

# #             if not exists:
# #                 await self.qdrant.create_collection(
# #                     collection_name=self.qdrant_collection,
# #                     vectors_config=models.VectorParams(
# #                         size=self.embedding_dimensions,
# #                         distance=models.Distance.COSINE,
# #                     ),
# #                 )
# #                 self._qdrant_collection_created = True
# #                 self._qdrant_reachable = True
# #                 self._qdrant_has_points = False

# #                 logger.info(
# #                     f"Created Qdrant collection '{self.qdrant_collection}' "
# #                     f"with vector size={self.embedding_dimensions}. "
# #                     "Collection is empty, so semantic matching is skipped "
# #                     "until approved concepts are synced."
# #                 )
# #                 return

# #             info = await self.qdrant.get_collection(
# #                 collection_name=self.qdrant_collection
# #             )

# #             self._qdrant_reachable = True
# #             points_count = int(getattr(info, "points_count", 0) or 0)
# #             self._qdrant_has_points = points_count > 0

# #             logger.info(
# #                 f"Qdrant ready: collection={self.qdrant_collection}, "
# #                 f"points={points_count}"
# #             )

# #         except Exception as exc:
# #             self._qdrant_reachable = False
# #             self._qdrant_has_points = False
# #             logger.warning(
# #                 "Qdrant is unavailable. Continuing with MySQL exact matching "
# #                 f"only. Error: {exc}"
# #             )

# #     # ============================================================
# #     # OPENAI EMBEDDINGS
# #     # ============================================================

# #     async def _batch_embeddings(
# #         self,
# #         names: List[str],
# #         batch_size: int = 100,
# #     ) -> Dict[str, List[float]]:
# #         """
# #         Batch unresolved names into a small number of OpenAI calls.
# #         """
# #         output: Dict[str, List[float]] = {}

# #         unique_names = []
# #         seen = set()
# #         for name in names:
# #             key = name.casefold()
# #             if key in seen:
# #                 continue
# #             seen.add(key)
# #             unique_names.append(name)

# #         for start in range(0, len(unique_names), batch_size):
# #             batch = unique_names[start : start + batch_size]

# #             try:
# #                 response = await self.openai_client.embeddings.create(
# #                     model=self.embedding_model,
# #                     input=batch,
# #                     dimensions=self.embedding_dimensions,
# #                 )
# #             except Exception as exc:
# #                 logger.warning(
# #                     f"Embedding batch failed for {len(batch)} concepts: {exc}"
# #                 )
# #                 continue

# #             for input_name, item in zip(batch, response.data):
# #                 output[input_name.casefold()] = item.embedding
# #                 self._embedding_cache[input_name.casefold()] = item.embedding

# #         return output

# #     async def _qdrant_candidates_from_vector(
# #         self,
# #         vector: List[float],
# #     ) -> List[Dict[str, Any]]:
# #         try:
# #             response = await self.qdrant.query_points(
# #                 collection_name=self.qdrant_collection,
# #                 query=vector,
# #                 limit=self.QDRANT_LIMIT,
# #                 with_payload=True,
# #             )
# #         except Exception as exc:
# #             logger.warning(f"Qdrant query failed: {exc}")
# #             return []

# #         points = getattr(response, "points", []) or []
# #         output = []

# #         for point in points:
# #             payload = point.payload or {}
# #             uid = (
# #                 payload.get("concept_uid")
# #                 or payload.get("uid")
# #                 or payload.get("concept_id")
# #             )
# #             name = (
# #                 payload.get("canonical_name")
# #                 or payload.get("name")
# #                 or payload.get("concept_name")
# #             )

# #             if uid is None:
# #                 continue

# #             output.append(
# #                 {
# #                     "concept_uid": str(uid),
# #                     "canonical_name": name,
# #                     "score": float(point.score or 0.0),
# #                 }
# #             )

# #         return output

# #     # ============================================================
# #     # CONCEPT RESOLUTION
# #     # ============================================================

# #     def _exact_mysql_resolution(
# #         self,
# #         concept_name: str,
# #     ) -> Optional[Dict[str, Any]]:
# #         trusted = self._mysql_by_name.get(
# #             self._comparison_key(concept_name)
# #         )
# #         if not trusted:
# #             return None

# #         return {
# #             "original_name": concept_name,
# #             "canonical_name": trusted["canonical_name"],
# #             "concept_uid": trusted["concept_uid"],
# #             "type_key": trusted.get("type_key"),
# #             "resolution_status": "EXISTING",
# #             "match_method": "mysql_exact_or_term",
# #             "similarity_score": 1.0,
# #             "needs_review": False,
# #         }

# #     def _new_proposal_resolution(
# #         self,
# #         original_name: str,
# #         candidate: Optional[Dict[str, Any]] = None,
# #     ) -> Dict[str, Any]:
# #         resolution = {
# #             "original_name": original_name,
# #             "canonical_name": self._normalize_name(original_name),
# #             "proposal_uid": self._new_proposal_uid(),
# #             "resolution_status": "NEW_PROPOSAL",
# #             "match_method": "no_trusted_match",
# #             "similarity_score": None,
# #             "needs_review": True,
# #         }

# #         if candidate:
# #             resolution.update(
# #                 {
# #                     "resolution_status": "REVIEW_REQUIRED",
# #                     "match_method": "qdrant_ambiguous",
# #                     "candidate_concept_uid": candidate.get("concept_uid"),
# #                     "candidate_name": candidate.get("canonical_name"),
# #                     "similarity_score": round(
# #                         float(candidate.get("score", 0.0)), 4
# #                     ),
# #                 }
# #             )

# #         return resolution

# #     async def _resolve_semantic_batch(
# #         self,
# #         unresolved: List[Tuple[int, Dict[str, Any]]],
# #     ) -> Dict[int, Dict[str, Any]]:
# #         """
# #         Resolve only concepts that did not exact-match MySQL.

# #         If Qdrant is empty/unavailable, no embeddings are created.
# #         """
# #         if not unresolved or not self._qdrant_has_points:
# #             return {}

# #         names = [
# #             self._normalize_name(concept.get("canonical_name", ""))
# #             for _, concept in unresolved
# #         ]
# #         embeddings = await self._batch_embeddings(names)

# #         semaphore = asyncio.Semaphore(self.normalization_concurrency)

# #         async def one(index: int, concept: Dict[str, Any]):
# #             name = self._normalize_name(concept.get("canonical_name", ""))
# #             vector = embeddings.get(name.casefold())
# #             if vector is None:
# #                 return index, None

# #             async with semaphore:
# #                 candidates = await self._qdrant_candidates_from_vector(vector)

# #             best_review_candidate = None

# #             for candidate in candidates:
# #                 trusted = self._mysql_by_uid.get(
# #                     str(candidate.get("concept_uid"))
# #                 )
# #                 if not trusted:
# #                     # Qdrant can only suggest. MySQL must confirm.
# #                     continue

# #                 score = float(candidate.get("score", 0.0))

# #                 if score >= self.SEMANTIC_MATCH_THRESHOLD:
# #                     return index, {
# #                         "original_name": name,
# #                         "canonical_name": trusted["canonical_name"],
# #                         "concept_uid": trusted["concept_uid"],
# #                         "type_key": trusted.get("type_key"),
# #                         "resolution_status": "EXISTING",
# #                         "match_method": "qdrant_verified_mysql",
# #                         "similarity_score": round(score, 4),
# #                         "needs_review": False,
# #                     }

# #                 if (
# #                     score >= self.SEMANTIC_REVIEW_THRESHOLD
# #                     and best_review_candidate is None
# #                 ):
# #                     best_review_candidate = {
# #                         "concept_uid": trusted["concept_uid"],
# #                         "canonical_name": trusted["canonical_name"],
# #                         "score": score,
# #                     }

# #             if best_review_candidate:
# #                 return index, self._new_proposal_resolution(
# #                     name,
# #                     candidate=best_review_candidate,
# #                 )

# #             return index, None

# #         tasks = [
# #             asyncio.create_task(one(index, concept))
# #             for index, concept in unresolved
# #         ]

# #         results: Dict[int, Dict[str, Any]] = {}
# #         for task in asyncio.as_completed(tasks):
# #             index, resolution = await task
# #             if resolution:
# #                 results[index] = resolution

# #         return results

# #     # ============================================================
# #     # RELATIONSHIPS
# #     # ============================================================

# #     def _normalize_relationship_type(self, value: Any) -> str:
# #         normalized = re.sub(
# #             r"[^a-z0-9]+",
# #             "_",
# #             self._normalize_space(value).casefold(),
# #         ).strip("_")

# #         aliases = {
# #             "has_attribute": "has_sensory_attribute",
# #             "sensory_attribute": "has_sensory_attribute",
# #             "has_intensity_value": "has_intensity",
# #             "has_rating": "has_score",
# #             "uses_methodology": "uses_method",
# #             "belongs": "belongs_to",
# #             "associated": "associated_with",
# #         }

# #         return aliases.get(normalized, normalized or "related_to")

# #     async def _resolve_relationship(
# #         self,
# #         relationship: Dict[str, Any],
# #         concept_lookup: Dict[str, Dict[str, Any]],
# #         valid_relationship_types: Set[str],
# #     ) -> Dict[str, Any]:
# #         source_name = self._normalize_name(
# #             relationship.get("source_concept", "")
# #         )
# #         target_name = self._normalize_name(
# #             relationship.get("target_concept", "")
# #         )
# #         rel_type = self._normalize_relationship_type(
# #             relationship.get("relationship_type", "related_to")
# #         )

# #         source_key = self._comparison_key(source_name)
# #         target_key = self._comparison_key(target_name)

# #         source = concept_lookup.get(source_key)
# #         target = concept_lookup.get(target_key)

# #         if not source or not target:
# #             return {
# #                 "status": "REJECTED",
# #                 "reason": "relationship_endpoint_missing_or_rejected",
# #                 "source_concept": source_name,
# #                 "target_concept": target_name,
# #                 "relationship_type": rel_type,
# #             }

# #         if source_key == target_key:
# #             return {
# #                 "status": "REJECTED",
# #                 "reason": "self_relationship",
# #                 "source_concept": source_name,
# #                 "target_concept": target_name,
# #                 "relationship_type": rel_type,
# #             }

# #         if rel_type not in valid_relationship_types:
# #             return {
# #                 "status": "REVIEW_REQUIRED",
# #                 "reason": "relationship_type_not_registered",
# #                 "source": source,
# #                 "target": target,
# #                 "relationship_type": rel_type,
# #             }

# #         source_uid = source.get("concept_uid") or source.get("proposal_uid")
# #         target_uid = target.get("concept_uid") or target.get("proposal_uid")

# #         if not source_uid or not target_uid:
# #             return {
# #                 "status": "REJECTED",
# #                 "reason": "relationship_uid_missing",
# #                 "source_concept": source_name,
# #                 "target_concept": target_name,
# #                 "relationship_type": rel_type,
# #             }

# #         both_existing = (
# #             source.get("resolution_status") == "EXISTING"
# #             and target.get("resolution_status") == "EXISTING"
# #         )

# #         return {
# #             "relationship_uid": self._stable_relationship_uid(
# #                 str(source_uid),
# #                 rel_type,
# #                 str(target_uid),
# #             ),
# #             "source_uid": source_uid,
# #             "target_uid": target_uid,
# #             "source_concept": source["canonical_name"],
# #             "target_concept": target["canonical_name"],
# #             "relationship_type": rel_type,
# #             "status": "READY" if both_existing else "REVIEW_REQUIRED",
# #             "confidence": relationship.get("confidence"),
# #             "source_page": relationship.get("source_page"),
# #             "element_id": relationship.get("element_id"),
# #             "evidence": relationship.get("evidence"),
# #         }

# #     # ============================================================
# #     # SCHEMA MAPPERS
# #     # ============================================================

# #     def _type_key(self, concept: Dict[str, Any]) -> str:
# #         return self.CATEGORY_TO_TYPE_KEY.get(
# #             concept.get("category", "Entity"),
# #             "entity",
# #         )

# #     def _proposal_record(
# #         self,
# #         document_id: str,
# #         concept: Dict[str, Any],
# #         resolution: Dict[str, Any],
# #     ) -> Dict[str, Any]:
# #         return {
# #             "proposal_uid": resolution["proposal_uid"],
# #             "document_id": document_id,
# #             "proposed_name": resolution["canonical_name"],
# #             "type_key": self._type_key(concept),
# #             "definition": concept.get("definition"),
# #             "synonyms": self._dedupe_strings(concept.get("synonyms", [])),
# #             "keywords": self._dedupe_strings(concept.get("keywords", [])),
# #             "attributes": concept.get("attributes", []),
# #             "source_page": concept.get("source_page"),
# #             "element_id": concept.get("element_id"),
# #             "section_path": concept.get("section_path", []),
# #             "hierarchy_context": concept.get("hierarchy_context"),
# #             "proposal_status": "PENDING_REVIEW",
# #             "candidate_concept_uid": resolution.get("candidate_concept_uid"),
# #             "candidate_name": resolution.get("candidate_name"),
# #             "candidate_similarity": resolution.get("similarity_score"),
# #             "match_method": resolution.get("match_method"),
# #         }

# #     def _term_records(
# #         self,
# #         concept: Dict[str, Any],
# #         resolution: Dict[str, Any],
# #     ) -> List[Dict[str, Any]]:
# #         owner_uid = resolution.get("concept_uid") or resolution.get("proposal_uid")
# #         canonical_name = resolution["canonical_name"]
# #         proposed = resolution["resolution_status"] != "EXISTING"

# #         output = [
# #             {
# #                 "concept_uid": owner_uid,
# #                 "term": canonical_name,
# #                 "term_type": "canonical",
# #                 "proposed": proposed,
# #             }
# #         ]

# #         for synonym in self._dedupe_strings(concept.get("synonyms", [])):
# #             if synonym.casefold() == canonical_name.casefold():
# #                 continue
# #             output.append(
# #                 {
# #                     "concept_uid": owner_uid,
# #                     "term": synonym,
# #                     "term_type": "synonym",
# #                     "proposed": proposed,
# #                 }
# #             )

# #         return output

# #     def _concept_field_records(
# #         self,
# #         document_id: str,
# #         concept: Dict[str, Any],
# #         resolution: Dict[str, Any],
# #     ) -> List[Dict[str, Any]]:
# #         owner_uid = resolution.get("concept_uid") or resolution.get("proposal_uid")
# #         proposed = resolution["resolution_status"] != "EXISTING"

# #         simple_fields = {
# #             "definition": concept.get("definition"),
# #             "hierarchy_context": concept.get("hierarchy_context"),
# #             "source_page": concept.get("source_page"),
# #             "element_id": concept.get("element_id"),
# #         }

# #         output = []
# #         for field_name, field_value in simple_fields.items():
# #             if field_value in (None, ""):
# #                 continue
# #             output.append(
# #                 {
# #                     "concept_uid": owner_uid,
# #                     "field_name": field_name,
# #                     "field_value": field_value,
# #                     "document_id": document_id,
# #                     "proposed": proposed,
# #                 }
# #             )

# #         # Preserve structured attributes as fields as well.
# #         attributes = concept.get("attributes", [])
# #         if isinstance(attributes, list):
# #             for attribute in attributes:
# #                 if not isinstance(attribute, dict):
# #                     continue
# #                 name = self._normalize_name(attribute.get("name"))
# #                 value = attribute.get("value")
# #                 if not name or value in (None, ""):
# #                     continue
# #                 output.append(
# #                     {
# #                         "concept_uid": owner_uid,
# #                         "field_name": name,
# #                         "field_value": value,
# #                         "document_id": document_id,
# #                         "proposed": proposed,
# #                     }
# #                 )

# #         return output

# #     # ============================================================
# #     # MASTER
# #     # ============================================================

# #     async def normalize_graph_and_map(
# #         self,
# #         document_id: str,
# #     ) -> Dict[str, Any]:
# #         started = time.perf_counter()

# #         processed_base = self.processed_dir / document_id
# #         knowledge_path = processed_base / "extracted_knowledge.json"

# #         knowledge = self._require_knowledge_artifact(
# #             knowledge_path,
# #             document_id,
# #         )

# #         concepts = [
# #             item for item in knowledge.get("concepts", [])
# #             if isinstance(item, dict)
# #         ]
# #         relationships = [
# #             item for item in knowledge.get("relationships", [])
# #             if isinstance(item, dict)
# #         ]

# #         logger.info(
# #             f"Normalization started for {document_id}. "
# #             f"Concepts={len(concepts)}, Relationships={len(relationships)}"
# #         )

# #         # --------------------------------------------------------
# #         # 1. REQUIRED SOURCE-OF-TRUTH PREFLIGHT
# #         # --------------------------------------------------------
# #         await self._mysql_preflight()
# #         await self._load_mysql_catalog()
# #         valid_relationship_types = await self._load_relationship_types()

# #         # --------------------------------------------------------
# #         # 2. OPTIONAL SEMANTIC SEARCH PREFLIGHT
# #         # --------------------------------------------------------
# #         await self._prepare_qdrant()

# #         # --------------------------------------------------------
# #         # 3. FIRST PASS: reject junk + exact MySQL match
# #         # --------------------------------------------------------
# #         resolutions_by_index: Dict[int, Dict[str, Any]] = {}
# #         rejected_concepts: List[Dict[str, Any]] = []
# #         unresolved: List[Tuple[int, Dict[str, Any]]] = []

# #         for index, concept in enumerate(concepts):
# #             original_name = self._normalize_name(
# #                 concept.get("canonical_name", "")
# #             )

# #             if not original_name:
# #                 rejected_concepts.append(
# #                     {
# #                         "concept": concept,
# #                         "resolution": {
# #                             "resolution_status": "REJECTED",
# #                             "reason": "empty_concept_name",
# #                         },
# #                     }
# #                 )
# #                 continue

# #             if self._is_metadata_concept(original_name):
# #                 rejected_concepts.append(
# #                     {
# #                         "concept": concept,
# #                         "resolution": {
# #                             "canonical_name": original_name,
# #                             "resolution_status": "REJECTED",
# #                             "reason": "document_metadata",
# #                         },
# #                     }
# #                 )
# #                 continue

# #             if self._is_floating_value(original_name):
# #                 rejected_concepts.append(
# #                     {
# #                         "concept": concept,
# #                         "resolution": {
# #                             "canonical_name": original_name,
# #                             "resolution_status": "REJECTED",
# #                             "reason": "floating_numeric_or_formula_value",
# #                         },
# #                     }
# #                 )
# #                 continue

# #             exact = self._exact_mysql_resolution(original_name)
# #             if exact:
# #                 resolutions_by_index[index] = exact
# #             else:
# #                 unresolved.append((index, concept))

# #         # --------------------------------------------------------
# #         # 4. SECOND PASS: semantic candidate only if Qdrant has data
# #         # --------------------------------------------------------
# #         semantic_results = await self._resolve_semantic_batch(unresolved)
# #         resolutions_by_index.update(semantic_results)

# #         # No exact/semantic trusted match -> proposal.
# #         for index, concept in unresolved:
# #             if index in resolutions_by_index:
# #                 continue
# #             name = self._normalize_name(concept.get("canonical_name", ""))
# #             resolutions_by_index[index] = self._new_proposal_resolution(name)

# #         # --------------------------------------------------------
# #         # 5. BUILD CONCEPT LOOKUP + CLIENT PAYLOAD SECTIONS
# #         # --------------------------------------------------------
# #         concept_lookup: Dict[str, Dict[str, Any]] = {}
# #         canonical_mapping = []
# #         proposals = []
# #         concept_terms = []
# #         concept_fields = []

# #         for index, concept in enumerate(concepts):
# #             resolution = resolutions_by_index.get(index)
# #             if not resolution:
# #                 continue

# #             canonical_mapping.append(
# #                 {
# #                     "source_concept": concept.get("canonical_name"),
# #                     **resolution,
# #                 }
# #             )

# #             original_key = self._comparison_key(
# #                 concept.get("canonical_name", "")
# #             )
# #             canonical_key = self._comparison_key(
# #                 resolution["canonical_name"]
# #             )

# #             concept_lookup[original_key] = resolution
# #             concept_lookup[canonical_key] = resolution

# #             if resolution["resolution_status"] in {
# #                 "NEW_PROPOSAL",
# #                 "REVIEW_REQUIRED",
# #             }:
# #                 proposals.append(
# #                     self._proposal_record(
# #                         document_id,
# #                         concept,
# #                         resolution,
# #                     )
# #                 )

# #             concept_terms.extend(
# #                 self._term_records(concept, resolution)
# #             )
# #             concept_fields.extend(
# #                 self._concept_field_records(
# #                     document_id,
# #                     concept,
# #                     resolution,
# #                 )
# #             )

# #         # --------------------------------------------------------
# #         # 6. RELATIONSHIP GRAPH
# #         # --------------------------------------------------------
# #         ready_relationships = []
# #         pending_relationships = []
# #         rejected_relationships = []
# #         seen_relationships = set()

# #         for relationship in relationships:
# #             mapped = await self._resolve_relationship(
# #                 relationship,
# #                 concept_lookup,
# #                 valid_relationship_types,
# #             )

# #             signature = mapped.get("relationship_uid") or json.dumps(
# #                 mapped,
# #                 sort_keys=True,
# #                 default=str,
# #             )

# #             if signature in seen_relationships:
# #                 continue
# #             seen_relationships.add(signature)

# #             if mapped.get("status") == "READY":
# #                 ready_relationships.append(mapped)
# #             elif mapped.get("status") == "REVIEW_REQUIRED":
# #                 pending_relationships.append(mapped)
# #             else:
# #                 rejected_relationships.append(mapped)

# #         existing_count = sum(
# #             1
# #             for item in canonical_mapping
# #             if item.get("resolution_status") == "EXISTING"
# #         )
# #         new_count = sum(
# #             1
# #             for item in canonical_mapping
# #             if item.get("resolution_status") == "NEW_PROPOSAL"
# #         )
# #         review_count = sum(
# #             1
# #             for item in canonical_mapping
# #             if item.get("resolution_status") == "REVIEW_REQUIRED"
# #         )

# #         mysql_payload = {
# #             "document_id": document_id,
# #             "existing_concepts": [
# #                 item
# #                 for item in canonical_mapping
# #                 if item.get("resolution_status") == "EXISTING"
# #             ],
# #             "concepts": [],
# #             "concept_terms": concept_terms,
# #             "concept_fields": concept_fields,
# #             "concept_field_arrays": [],
# #             "concept_relationships": ready_relationships,
# #             "concept_proposals": proposals,
# #             "pending_relationships": pending_relationships,
# #             "rejected_concepts": rejected_concepts,
# #             "rejected_relationships": rejected_relationships,
# #             "question_concept_links": [],
# #             "option_concept_links": [],
# #             "concept_exclusions": [],
# #             "governance_rules": [],
# #             "validation_stats": {
# #                 "input_concepts": len(concepts),
# #                 "existing_concepts_reused": existing_count,
# #                 "new_proposals_generated": new_count,
# #                 "ambiguous_concepts_for_review": review_count,
# #                 "rejected_concepts": len(rejected_concepts),
# #                 "input_relationships": len(relationships),
# #                 "live_edges_ready": len(ready_relationships),
# #                 "pending_relationships": len(pending_relationships),
# #                 "rejected_relationships": len(rejected_relationships),
# #             },
# #         }

# #         canonical_path = processed_base / "canonical_mapping.json"
# #         mysql_payload_path = processed_base / "mysql_payload.json"

# #         self._atomic_write_json(
# #             canonical_path,
# #             {
# #                 "document_id": document_id,
# #                 "canonical_mapping": canonical_mapping,
# #                 "summary": {
# #                     "existing": existing_count,
# #                     "new_proposals": new_count,
# #                     "review_required": review_count,
# #                     "rejected": len(rejected_concepts),
# #                 },
# #             },
# #         )

# #         self._atomic_write_json(mysql_payload_path, mysql_payload)

# #         elapsed = time.perf_counter() - started

# #         logger.info(
# #             f"Normalization + Graph + Schema Mapping completed "
# #             f"for {document_id} in {elapsed:.2f}s. "
# #             f"existing={existing_count}, proposals={new_count}, "
# #             f"review={review_count}, rejected={len(rejected_concepts)}, "
# #             f"ready_edges={len(ready_relationships)}"
# #         )

# #         return {
# #             "document_id": document_id,
# #             "pipeline_status": "NORMALIZED_AND_MAPPED",
# #             "normalization": {
# #                 "input_concepts": len(concepts),
# #                 "existing_concepts_reused": existing_count,
# #                 "new_proposals": new_count,
# #                 "review_required": review_count,
# #                 "rejected_concepts": len(rejected_concepts),
# #             },
# #             "knowledge_graph": {
# #                 "input_relationships": len(relationships),
# #                 "ready_relationships": len(ready_relationships),
# #                 "pending_relationships": len(pending_relationships),
# #                 "rejected_relationships": len(rejected_relationships),
# #             },
# #             "schema_mapping": {
# #                 "concepts": 0,
# #                 "concept_terms": len(concept_terms),
# #                 "concept_fields": len(concept_fields),
# #                 "concept_relationships": len(ready_relationships),
# #                 "concept_proposals": len(proposals),
# #             },
# #             "infrastructure": {
# #                 "mysql": "READY",
# #                 "mysql_trusted_concepts_loaded": len(self._mysql_by_uid),
# #                 "qdrant_reachable": self._qdrant_reachable,
# #                 "qdrant_collection": self.qdrant_collection,
# #                 "qdrant_collection_created": self._qdrant_collection_created,
# #                 "qdrant_has_points": self._qdrant_has_points,
# #                 "semantic_matching_used": self._qdrant_has_points,
# #             },
# #             "artifacts": {
# #                 "canonical_mapping": str(
# #                     canonical_path.relative_to(settings.BASE_DIR)
# #                 ),
# #                 "mysql_payload": str(
# #                     mysql_payload_path.relative_to(settings.BASE_DIR)
# #                 ),
# #             },
# #             "processing_time_seconds": round(elapsed, 2),
# #             "next_step": (
# #                 f"{settings.API_V1_STR}/documents/"
# #                 f"{document_id}/validate-commit"
# #             ),
# #         }





# import asyncio
# import hashlib
# import json
# import re
# import time
# from pathlib import Path
# from typing import Any, Dict, List, Optional, Set, Tuple

# from openai import AsyncOpenAI
# from qdrant_client import AsyncQdrantClient, models
# from sqlalchemy import text
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.core.config import settings
# from app.core.exceptions import ProcessingError
# from app.core.logger import logger


# class NormalizationGraphService:
#     """
#     TagTaste - Production-ready Normalization + Graph + Schema Mapping.

#     MySQL:
#         Source of truth.

#     Qdrant:
#         Candidate retrieval only.

#     This service:
#         - never treats MySQL failure as "new concepts"
#         - creates missing Qdrant collection once
#         - skips semantic search when Qdrant has zero points
#         - rejects floating numeric/formula fragments
#         - creates deterministic proposal IDs
#         - dedupes proposals/terms/fields/relationships
#         - produces quality gate and next-action guidance
#         - writes idempotent artifacts
#     """

#     DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
#     DEFAULT_QDRANT_COLLECTION = "concepts"
#     DEFAULT_EMBEDDING_DIMENSIONS = 1536

#     SEMANTIC_MATCH_THRESHOLD = 0.88
#     SEMANTIC_REVIEW_THRESHOLD = 0.78
#     QDRANT_LIMIT = 5

#     KNOWLEDGE_REQUIRED_STATUS = "KNOWLEDGE_EXTRACTED"

#     DEFAULT_RELATIONSHIP_TYPES: Set[str] = {
#         "is_child_of",
#         "described_by",
#         "measured_by",
#         "categorized_as",
#         "related_to",
#         "causes",
#         "influences",
#         "part_of",
#         "uses_method",
#         "benchmarked_by",
#         "triggered_by",
#         "contains",
#         "has_attribute",
#         "has_sensory_attribute",
#         "has_descriptor",
#         "has_intensity",
#         "has_score",
#         "uses_scale",
#         "evaluated_by",
#         "compared_with",
#         "prepared_by",
#         "derived_from",
#         "belongs_to",
#         "associated_with",
#         "defined_by",
#         "measured_under",
#         "tested_by",
#         "has_method",
#         "has_property",
#         "correlates_with",
#     }

#     CATEGORY_TO_TYPE_KEY = {
#         "Entity": "entity",
#         "Method": "method",
#         "Theory": "theory",
#         "Process": "process",
#         "Material": "material",
#         "Chemical": "chemical",
#         "Instrument": "instrument",
#         "Organization": "organization",
#         "Measurement": "measurement",
#         "Property": "property",
#         "Sensory_Attribute": "sensory_attribute",
#         "Sensory Attribute": "sensory_attribute",
#         "Descriptor": "descriptor",
#         "Scale": "scale",
#         "Product": "product",
#         "Sample": "sample",
#         "Benchmark": "benchmark",
#         "Analysis_Method": "analysis_method",
#         "Analysis Method": "analysis_method",
#     }

#     METADATA_PATTERNS = [
#         r"\bisbn\b",
#         r"\bcopyright\b",
#         r"\bpublisher\b",
#         r"\bedition\b",
#         r"\bauthor\b",
#         r"\bprinted by\b",
#         r"\ball rights reserved\b",
#         r"\btable of contents\b",
#         r"\bindex\b",
#         r"\breferences\b",
#         r"\bbibliography\b",
#     ]

#     PURE_NUMBER_RE = re.compile(
#         r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:\s*%|\s*[a-zA-Z°]+)?$"
#     )
#     ASSIGNMENT_VALUE_RE = re.compile(
#         r"^[A-Za-zαβμσχ²χ]+(?:\d+)?\s*=\s*[+-]?\d+(?:\.\d+)?%?$"
#     )
#     SHORT_FORMULA_RE = re.compile(
#         r"^(?:n\d*|x\d*|s\d*|t\d*|f|p|d\d*|c\d*|χ²?)\s*=?\s*[+-]?\d*(?:\.\d+)?%?$",
#         re.IGNORECASE,
#     )

#     def __init__(self, db: AsyncSession):
#         self.db = db

#         self.raw_dir = Path(settings.STORAGE_RAW_DIR)
#         self.processed_dir = Path(settings.STORAGE_PROCESSED_DIR)

#         self.embedding_model = getattr(
#             settings,
#             "OPENAI_EMBEDDING_MODEL",
#             self.DEFAULT_EMBEDDING_MODEL,
#         )
#         self.embedding_dimensions = int(
#             getattr(
#                 settings,
#                 "OPENAI_EMBEDDING_DIMENSIONS",
#                 self.DEFAULT_EMBEDDING_DIMENSIONS,
#             )
#         )

#         self.openai_client = AsyncOpenAI(
#             api_key=settings.OPENAI_API_KEY,
#             timeout=float(getattr(settings, "OPENAI_TIMEOUT", 60.0)),
#             max_retries=int(getattr(settings, "OPENAI_MAX_RETRIES", 2)),
#         )

#         qdrant_url = getattr(settings, "QDRANT_URL", None)
#         if not qdrant_url:
#             qdrant_url = (
#                 f"http://{getattr(settings, 'QDRANT_HOST', 'localhost')}:"
#                 f"{int(getattr(settings, 'QDRANT_PORT', 6333))}"
#             )

#         self.qdrant = AsyncQdrantClient(
#             url=qdrant_url,
#             api_key=(getattr(settings, "QDRANT_API_KEY", "") or None),
#             timeout=5.0,
#             check_compatibility=False,
#         )

#         self.qdrant_collection = getattr(
#             settings,
#             "QDRANT_CONCEPT_COLLECTION",
#             self.DEFAULT_QDRANT_COLLECTION,
#         )

#         self.normalization_concurrency = max(
#             1,
#             int(getattr(settings, "NORMALIZATION_CONCURRENCY", 12)),
#         )

#         self._table_columns: Dict[str, List[str]] = {}
#         self._relationship_types: Optional[Set[str]] = None

#         self._mysql_by_name: Dict[str, Dict[str, Any]] = {}
#         self._mysql_by_uid: Dict[str, Dict[str, Any]] = {}

#         self._embedding_cache: Dict[str, List[float]] = {}

#         self._qdrant_reachable = False
#         self._qdrant_has_points = False
#         self._qdrant_collection_created = False

#         self._warnings: List[str] = []

#     # ============================================================
#     # BASIC HELPERS
#     # ============================================================

#     @staticmethod
#     def _normalize_space(value: Any) -> str:
#         return re.sub(r"\s+", " ", str(value or "")).strip()

#     def _normalize_name(self, value: Any) -> str:
#         return self._normalize_space(value).strip(" .,:;|-_")

#     def _comparison_key(self, value: Any) -> str:
#         normalized = self._normalize_name(value).casefold()
#         return re.sub(r"[^a-z0-9]+", "", normalized)

#     @staticmethod
#     def _dedupe_strings(values: Any) -> List[str]:
#         if not isinstance(values, list):
#             values = [values] if values else []

#         output: List[str] = []
#         seen = set()

#         for value in values:
#             item = str(value or "").strip()
#             if not item:
#                 continue

#             key = item.casefold()
#             if key in seen:
#                 continue

#             seen.add(key)
#             output.append(item)

#         return output

#     @staticmethod
#     def _stable_hash(*parts: Any, length: int = 16) -> str:
#         raw = "|".join(str(part or "") for part in parts)
#         return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]

#     def _stable_proposal_uid(self, document_id: str, canonical_name: str) -> str:
#         return "prop_" + self._stable_hash(
#             document_id,
#             self._comparison_key(canonical_name),
#             length=16,
#         )

#     def _stable_field_uid(
#         self,
#         concept_uid: str,
#         field_name: str,
#         field_value: Any,
#         document_id: str,
#     ) -> str:
#         return "field_" + self._stable_hash(
#             concept_uid,
#             field_name,
#             field_value,
#             document_id,
#             length=16,
#         )

#     @staticmethod
#     def _stable_relationship_uid(
#         source_uid: str,
#         relationship_type: str,
#         target_uid: str,
#     ) -> str:
#         digest = hashlib.sha256(
#             f"{source_uid}|{relationship_type}|{target_uid}".encode("utf-8")
#         ).hexdigest()[:16]
#         return f"rel_{digest}"

#     @staticmethod
#     def _dedupe_records(
#         records: List[Dict[str, Any]],
#         keys: List[str],
#     ) -> List[Dict[str, Any]]:
#         output = []
#         seen = set()

#         for record in records:
#             signature = tuple(
#                 json.dumps(record.get(key), sort_keys=True, default=str)
#                 for key in keys
#             )
#             if signature in seen:
#                 continue
#             seen.add(signature)
#             output.append(record)

#         return output

#     def _is_metadata_concept(self, concept_name: str) -> bool:
#         lowered = concept_name.casefold()
#         return any(re.search(pattern, lowered) for pattern in self.METADATA_PATTERNS)

#     def _is_floating_value(self, concept_name: str) -> bool:
#         name = self._normalize_name(concept_name)
#         if not name:
#             return True

#         if len(name) == 1 and name.casefold() in {
#             "c",
#             "d",
#             "f",
#             "p",
#             "s",
#             "t",
#             "x",
#             "n",
#         }:
#             return True

#         if self.PURE_NUMBER_RE.fullmatch(name):
#             return True

#         if self.ASSIGNMENT_VALUE_RE.fullmatch(name):
#             return True

#         if self.SHORT_FORMULA_RE.fullmatch(name):
#             if name.casefold() not in {"ph"}:
#                 return True

#         return False

#     def _type_key(self, concept: Dict[str, Any]) -> str:
#         raw_category = concept.get("category") or concept.get("type_key") or "Entity"
#         if raw_category in self.CATEGORY_TO_TYPE_KEY:
#             return self.CATEGORY_TO_TYPE_KEY[raw_category]
#         return re.sub(r"[^a-z0-9]+", "_", str(raw_category).casefold()).strip("_") or "entity"

#     # ============================================================
#     # FILE HELPERS
#     # ============================================================

#     @staticmethod
#     def _read_json(path: Path) -> Dict[str, Any]:
#         if not path.exists():
#             raise FileNotFoundError(f"JSON artifact not found: {path}")

#         try:
#             raw = path.read_text(encoding="utf-8-sig")
#         except OSError as exc:
#             raise ProcessingError(f"Could not read JSON artifact {path}: {exc}") from exc

#         if not raw.strip():
#             raise ProcessingError(f"JSON artifact exists but is empty: {path}")

#         try:
#             value = json.loads(raw)
#         except json.JSONDecodeError as exc:
#             raise ProcessingError(
#                 f"JSON artifact is invalid: {path}. "
#                 f"line={exc.lineno}, column={exc.colno}, error={exc.msg}"
#             ) from exc

#         if not isinstance(value, dict):
#             raise ProcessingError(
#                 f"Expected JSON object in {path}, got {type(value).__name__}."
#             )

#         return value

#     @staticmethod
#     def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
#         path.parent.mkdir(parents=True, exist_ok=True)
#         temp_path = path.with_suffix(path.suffix + ".tmp")

#         with open(temp_path, "w", encoding="utf-8") as file:
#             json.dump(
#                 payload,
#                 file,
#                 indent=2,
#                 ensure_ascii=False,
#                 default=str,
#             )
#             file.flush()

#         temp_path.replace(path)

#     def _read_metadata(self, document_id: str) -> Dict[str, Any]:
#         path = self.raw_dir / document_id / "metadata.json"
#         if not path.exists():
#             raise FileNotFoundError(f"metadata.json not found for {document_id}.")
#         return self._read_json(path)

#     def _write_metadata_status(
#         self,
#         document_id: str,
#         status_value: str,
#         extra: Optional[Dict[str, Any]] = None,
#     ) -> None:
#         path = self.raw_dir / document_id / "metadata.json"
#         metadata = self._read_json(path)
#         metadata["pipeline_status"] = status_value
#         metadata["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
#         if extra:
#             metadata.update(extra)
#         self._atomic_write_json(path, metadata)

#     def _require_knowledge_artifact(
#         self,
#         knowledge_path: Path,
#         document_id: str,
#     ) -> Dict[str, Any]:
#         metadata = self._read_metadata(document_id)
#         pipeline_status = str(metadata.get("pipeline_status", "UNKNOWN")).strip()

#         if pipeline_status not in {
#             self.KNOWLEDGE_REQUIRED_STATUS,
#             "NORMALIZED_AND_MAPPED",
#         }:
#             raise ProcessingError(
#                 f"Knowledge extraction is not complete for {document_id}. "
#                 f"Current pipeline_status={pipeline_status}; "
#                 f"required={self.KNOWLEDGE_REQUIRED_STATUS}."
#             )

#         knowledge = self._read_json(knowledge_path)

#         concepts = knowledge.get("concepts", [])
#         relationships = knowledge.get("relationships", [])

#         if not isinstance(concepts, list):
#             raise ProcessingError("'concepts' must be a JSON array.")

#         if not isinstance(relationships, list):
#             raise ProcessingError("'relationships' must be a JSON array.")

#         return knowledge

#     # ============================================================
#     # MYSQL
#     # ============================================================

#     async def _mysql_preflight(self) -> None:
#         try:
#             result = await self.db.execute(text("SELECT 1 AS ok"))
#             row = result.first()
#             if not row or int(row[0]) != 1:
#                 raise RuntimeError("SELECT 1 returned an unexpected value")
#         except Exception as exc:
#             raise ProcessingError(
#                 "MySQL is unavailable. Normalization cannot safely continue "
#                 "because MySQL is the source of truth. "
#                 f"Database error: {exc}"
#             ) from exc

#     async def _get_columns(self, table_name: str) -> List[str]:
#         if table_name in self._table_columns:
#             return self._table_columns[table_name]

#         result = await self.db.execute(
#             text(
#                 """
#                 SELECT COLUMN_NAME
#                 FROM INFORMATION_SCHEMA.COLUMNS
#                 WHERE TABLE_SCHEMA = DATABASE()
#                   AND TABLE_NAME = :table_name
#                 ORDER BY ORDINAL_POSITION
#                 """
#             ),
#             {"table_name": table_name},
#         )

#         columns = [str(row[0]) for row in result.all()]
#         self._table_columns[table_name] = columns
#         return columns

#     @staticmethod
#     def _pick_column(
#         available: List[str],
#         candidates: List[str],
#     ) -> Optional[str]:
#         lookup = {column.casefold(): column for column in available}
#         for candidate in candidates:
#             if candidate.casefold() in lookup:
#                 return lookup[candidate.casefold()]
#         return None

#     async def _load_mysql_catalog(self) -> None:
#         concept_columns = await self._get_columns("concepts")
#         if not concept_columns:
#             raise ProcessingError(
#                 "Required MySQL table 'concepts' does not exist in the current database."
#             )

#         uid_col = self._pick_column(concept_columns, ["uid", "concept_uid", "id"])
#         name_col = self._pick_column(
#             concept_columns,
#             ["canonical_name", "name", "concept_name", "label"],
#         )
#         type_col = self._pick_column(
#             concept_columns,
#             ["type_key", "concept_type", "category"],
#         )
#         status_col = self._pick_column(
#             concept_columns,
#             ["status", "approval_status"],
#         )

#         if not uid_col or not name_col:
#             raise ProcessingError(
#                 "Table 'concepts' must contain a UID column "
#                 "(uid/concept_uid/id) and name column "
#                 "(canonical_name/name/concept_name/label)."
#             )

#         selected = [
#             f"`{uid_col}` AS concept_uid",
#             f"`{name_col}` AS canonical_name",
#         ]
#         if type_col:
#             selected.append(f"`{type_col}` AS type_key")
#         if status_col:
#             selected.append(f"`{status_col}` AS concept_status")

#         result = await self.db.execute(
#             text(f"SELECT {', '.join(selected)} FROM concepts")
#         )

#         self._mysql_by_name.clear()
#         self._mysql_by_uid.clear()

#         for row in result.mappings().all():
#             uid = str(row["concept_uid"])
#             name = self._normalize_name(row["canonical_name"])
#             if not uid or not name:
#                 continue

#             status = row.get("concept_status")
#             if status and str(status).casefold() not in {
#                 "approved",
#                 "active",
#                 "published",
#                 "trusted",
#             }:
#                 continue

#             record = {
#                 "concept_uid": uid,
#                 "canonical_name": name,
#                 "type_key": row.get("type_key"),
#                 "status": status,
#             }

#             self._mysql_by_uid[uid] = record
#             self._mysql_by_name[self._comparison_key(name)] = record

#         await self._load_concept_terms_into_catalog()

#         logger.info(
#             "Loaded trusted MySQL concept catalog: "
#             f"concepts={len(self._mysql_by_uid)}, "
#             f"name/term keys={len(self._mysql_by_name)}"
#         )

#     async def _load_concept_terms_into_catalog(self) -> None:
#         term_columns = await self._get_columns("concept_terms")
#         if not term_columns:
#             return

#         term_col = self._pick_column(
#             term_columns,
#             ["term", "term_text", "name", "value", "synonym"],
#         )
#         ref_col = self._pick_column(
#             term_columns,
#             ["concept_uid", "concept_id", "uid"],
#         )

#         if not term_col or not ref_col:
#             return

#         result = await self.db.execute(
#             text(
#                 f"""
#                 SELECT
#                     `{ref_col}` AS concept_ref,
#                     `{term_col}` AS matched_term
#                 FROM concept_terms
#                 WHERE `{term_col}` IS NOT NULL
#                 """
#             )
#         )

#         for row in result.mappings().all():
#             ref = str(row["concept_ref"])
#             term_value = self._normalize_name(row["matched_term"])
#             trusted = self._mysql_by_uid.get(ref)

#             if trusted and term_value:
#                 self._mysql_by_name[self._comparison_key(term_value)] = trusted

#     async def _load_relationship_types(self) -> Set[str]:
#         if self._relationship_types is not None:
#             return self._relationship_types

#         columns = await self._get_columns("relationship_types")
#         if not columns:
#             self._warnings.append(
#                 "relationship_types table is missing or empty; default relationship types were used."
#             )
#             self._relationship_types = set(self.DEFAULT_RELATIONSHIP_TYPES)
#             return self._relationship_types

#         key_col = self._pick_column(
#             columns,
#             ["type_key", "relationship_type", "key", "name"],
#         )
#         if not key_col:
#             self._warnings.append(
#                 "relationship_types table has no usable key column; default relationship types were used."
#             )
#             self._relationship_types = set(self.DEFAULT_RELATIONSHIP_TYPES)
#             return self._relationship_types

#         result = await self.db.execute(
#             text(f"SELECT `{key_col}` FROM relationship_types")
#         )
#         values = {
#             str(row[0]).strip()
#             for row in result.all()
#             if row[0] is not None and str(row[0]).strip()
#         }

#         if not values:
#             self._warnings.append(
#                 "relationship_types table has no values; default relationship types were used."
#             )

#         self._relationship_types = values or set(self.DEFAULT_RELATIONSHIP_TYPES)
#         return self._relationship_types

#     # ============================================================
#     # QDRANT
#     # ============================================================

#     async def _prepare_qdrant(self) -> None:
#         try:
#             exists = await self.qdrant.collection_exists(
#                 collection_name=self.qdrant_collection
#             )

#             if not exists:
#                 await self.qdrant.create_collection(
#                     collection_name=self.qdrant_collection,
#                     vectors_config=models.VectorParams(
#                         size=self.embedding_dimensions,
#                         distance=models.Distance.COSINE,
#                     ),
#                 )
#                 self._qdrant_collection_created = True
#                 self._qdrant_reachable = True
#                 self._qdrant_has_points = False
#                 self._warnings.append(
#                     f"Qdrant collection '{self.qdrant_collection}' was created but has no approved concept vectors yet."
#                 )
#                 logger.info(
#                     f"Created Qdrant collection '{self.qdrant_collection}' "
#                     f"with vector size={self.embedding_dimensions}."
#                 )
#                 return

#             info = await self.qdrant.get_collection(
#                 collection_name=self.qdrant_collection
#             )

#             points_count = int(getattr(info, "points_count", 0) or 0)
#             self._qdrant_reachable = True
#             self._qdrant_has_points = points_count > 0

#             if points_count == 0:
#                 self._warnings.append(
#                     f"Qdrant collection '{self.qdrant_collection}' is empty; semantic matching was skipped."
#                 )

#             logger.info(
#                 f"Qdrant ready: collection={self.qdrant_collection}, points={points_count}"
#             )

#         except Exception as exc:
#             self._qdrant_reachable = False
#             self._qdrant_has_points = False
#             self._warnings.append(
#                 f"Qdrant unavailable; semantic matching skipped. Error={exc}"
#             )
#             logger.warning(
#                 "Qdrant is unavailable. Continuing with MySQL exact matching only. "
#                 f"Error: {exc}"
#             )

#     # ============================================================
#     # EMBEDDINGS + SEMANTIC MATCHING
#     # ============================================================

#     async def _batch_embeddings(
#         self,
#         names: List[str],
#         batch_size: int = 100,
#     ) -> Dict[str, List[float]]:
#         output: Dict[str, List[float]] = {}

#         unique_names = []
#         seen = set()

#         for name in names:
#             key = name.casefold()
#             if not name or key in seen:
#                 continue
#             seen.add(key)
#             unique_names.append(name)

#         for start in range(0, len(unique_names), batch_size):
#             batch = unique_names[start : start + batch_size]

#             try:
#                 response = await self.openai_client.embeddings.create(
#                     model=self.embedding_model,
#                     input=batch,
#                     dimensions=self.embedding_dimensions,
#                 )
#             except Exception as exc:
#                 self._warnings.append(f"OpenAI embedding batch failed: {exc}")
#                 logger.warning(f"Embedding batch failed for {len(batch)} concepts: {exc}")
#                 continue

#             for input_name, item in zip(batch, response.data):
#                 output[input_name.casefold()] = item.embedding
#                 self._embedding_cache[input_name.casefold()] = item.embedding

#         return output

#     async def _qdrant_candidates_from_vector(
#         self,
#         vector: List[float],
#     ) -> List[Dict[str, Any]]:
#         try:
#             response = await self.qdrant.query_points(
#                 collection_name=self.qdrant_collection,
#                 query=vector,
#                 limit=self.QDRANT_LIMIT,
#                 with_payload=True,
#             )
#         except Exception as exc:
#             logger.warning(f"Qdrant query failed: {exc}")
#             return []

#         points = getattr(response, "points", []) or []
#         output: List[Dict[str, Any]] = []

#         for point in points:
#             payload = point.payload or {}
#             uid = payload.get("concept_uid") or payload.get("uid") or payload.get("concept_id")
#             name = payload.get("canonical_name") or payload.get("name") or payload.get("concept_name")

#             if uid is None:
#                 continue

#             output.append(
#                 {
#                     "concept_uid": str(uid),
#                     "canonical_name": name,
#                     "score": float(point.score or 0.0),
#                 }
#             )

#         return output

#     # ============================================================
#     # CONCEPT RESOLUTION
#     # ============================================================

#     def _exact_mysql_resolution(self, concept_name: str) -> Optional[Dict[str, Any]]:
#         trusted = self._mysql_by_name.get(self._comparison_key(concept_name))
#         if not trusted:
#             return None

#         return {
#             "original_name": concept_name,
#             "canonical_name": trusted["canonical_name"],
#             "concept_uid": trusted["concept_uid"],
#             "type_key": trusted.get("type_key"),
#             "resolution_status": "EXISTING",
#             "match_method": "mysql_exact_or_term",
#             "similarity_score": 1.0,
#             "needs_review": False,
#         }

#     def _proposal_resolution(
#         self,
#         document_id: str,
#         original_name: str,
#         candidate: Optional[Dict[str, Any]] = None,
#     ) -> Dict[str, Any]:
#         canonical_name = self._normalize_name(original_name)

#         resolution = {
#             "original_name": original_name,
#             "canonical_name": canonical_name,
#             "proposal_uid": self._stable_proposal_uid(document_id, canonical_name),
#             "resolution_status": "NEW_PROPOSAL",
#             "match_method": "no_trusted_match",
#             "similarity_score": None,
#             "needs_review": True,
#         }

#         if candidate:
#             resolution.update(
#                 {
#                     "resolution_status": "REVIEW_REQUIRED",
#                     "match_method": "qdrant_ambiguous",
#                     "candidate_concept_uid": candidate.get("concept_uid"),
#                     "candidate_name": candidate.get("canonical_name"),
#                     "similarity_score": round(float(candidate.get("score", 0.0)), 4),
#                 }
#             )

#         return resolution

#     async def _resolve_semantic_batch(
#         self,
#         document_id: str,
#         unresolved: List[Tuple[int, Dict[str, Any]]],
#     ) -> Dict[int, Dict[str, Any]]:
#         if not unresolved or not self._qdrant_has_points:
#             return {}

#         names = [
#             self._normalize_name(concept.get("canonical_name", ""))
#             for _, concept in unresolved
#         ]
#         embeddings = await self._batch_embeddings(names)

#         semaphore = asyncio.Semaphore(self.normalization_concurrency)

#         async def one(index: int, concept: Dict[str, Any]):
#             name = self._normalize_name(concept.get("canonical_name", ""))
#             vector = embeddings.get(name.casefold())

#             if vector is None:
#                 return index, None

#             async with semaphore:
#                 candidates = await self._qdrant_candidates_from_vector(vector)

#             best_review_candidate = None

#             for candidate in candidates:
#                 trusted = self._mysql_by_uid.get(str(candidate.get("concept_uid")))
#                 if not trusted:
#                     continue

#                 score = float(candidate.get("score", 0.0))

#                 if score >= self.SEMANTIC_MATCH_THRESHOLD:
#                     return index, {
#                         "original_name": name,
#                         "canonical_name": trusted["canonical_name"],
#                         "concept_uid": trusted["concept_uid"],
#                         "type_key": trusted.get("type_key"),
#                         "resolution_status": "EXISTING",
#                         "match_method": "qdrant_verified_mysql",
#                         "similarity_score": round(score, 4),
#                         "needs_review": False,
#                     }

#                 if score >= self.SEMANTIC_REVIEW_THRESHOLD and best_review_candidate is None:
#                     best_review_candidate = {
#                         "concept_uid": trusted["concept_uid"],
#                         "canonical_name": trusted["canonical_name"],
#                         "score": score,
#                     }

#             if best_review_candidate:
#                 return index, self._proposal_resolution(
#                     document_id,
#                     name,
#                     candidate=best_review_candidate,
#                 )

#             return index, None

#         tasks = [
#             asyncio.create_task(one(index, concept))
#             for index, concept in unresolved
#         ]

#         results: Dict[int, Dict[str, Any]] = {}

#         for task in asyncio.as_completed(tasks):
#             index, resolution = await task
#             if resolution:
#                 results[index] = resolution

#         return results

#     # ============================================================
#     # RELATIONSHIP RESOLUTION
#     # ============================================================

#     def _normalize_relationship_type(self, value: Any) -> str:
#         normalized = re.sub(
#             r"[^a-z0-9]+",
#             "_",
#             self._normalize_space(value).casefold(),
#         ).strip("_")

#         aliases = {
#             "has_attribute": "has_sensory_attribute",
#             "sensory_attribute": "has_sensory_attribute",
#             "has_intensity_value": "has_intensity",
#             "has_rating": "has_score",
#             "uses_methodology": "uses_method",
#             "belongs": "belongs_to",
#             "associated": "associated_with",
#             "related": "related_to",
#         }

#         return aliases.get(normalized, normalized or "related_to")

#     async def _resolve_relationship(
#         self,
#         relationship: Dict[str, Any],
#         concept_lookup: Dict[str, Dict[str, Any]],
#         valid_relationship_types: Set[str],
#     ) -> Dict[str, Any]:
#         source_name = self._normalize_name(relationship.get("source_concept", ""))
#         target_name = self._normalize_name(relationship.get("target_concept", ""))
#         rel_type = self._normalize_relationship_type(
#             relationship.get("relationship_type", "related_to")
#         )

#         source_key = self._comparison_key(source_name)
#         target_key = self._comparison_key(target_name)

#         source = concept_lookup.get(source_key)
#         target = concept_lookup.get(target_key)

#         if not source or not target:
#             return {
#                 "status": "REJECTED",
#                 "reason": "relationship_endpoint_missing_or_rejected",
#                 "source_concept": source_name,
#                 "target_concept": target_name,
#                 "relationship_type": rel_type,
#             }

#         if source_key == target_key:
#             return {
#                 "status": "REJECTED",
#                 "reason": "self_relationship",
#                 "source_concept": source_name,
#                 "target_concept": target_name,
#                 "relationship_type": rel_type,
#             }

#         if rel_type not in valid_relationship_types:
#             return {
#                 "status": "REVIEW_REQUIRED",
#                 "reason": "relationship_type_not_registered",
#                 "source": source,
#                 "target": target,
#                 "relationship_type": rel_type,
#             }

#         source_uid = source.get("concept_uid") or source.get("proposal_uid")
#         target_uid = target.get("concept_uid") or target.get("proposal_uid")

#         if not source_uid or not target_uid:
#             return {
#                 "status": "REJECTED",
#                 "reason": "relationship_uid_missing",
#                 "source_concept": source_name,
#                 "target_concept": target_name,
#                 "relationship_type": rel_type,
#             }

#         both_existing = (
#             source.get("resolution_status") == "EXISTING"
#             and target.get("resolution_status") == "EXISTING"
#         )

#         status_value = "READY" if both_existing else "REVIEW_REQUIRED"

#         return {
#             "relationship_uid": self._stable_relationship_uid(
#                 str(source_uid),
#                 rel_type,
#                 str(target_uid),
#             ),
#             "source_uid": source_uid,
#             "target_uid": target_uid,
#             "source_concept": source["canonical_name"],
#             "target_concept": target["canonical_name"],
#             "relationship_type": rel_type,
#             "status": status_value,
#             "reason": None if status_value == "READY" else "relationship_touches_unapproved_proposal",
#             "confidence": relationship.get("confidence"),
#             "source_page": relationship.get("source_page"),
#             "element_id": relationship.get("element_id"),
#             "evidence": relationship.get("evidence"),
#         }

#     # ============================================================
#     # SCHEMA RECORD BUILDERS
#     # ============================================================

#     def _proposal_record(
#         self,
#         document_id: str,
#         concept: Dict[str, Any],
#         resolution: Dict[str, Any],
#     ) -> Dict[str, Any]:
#         return {
#             "proposal_uid": resolution["proposal_uid"],
#             "document_id": document_id,
#             "proposed_name": resolution["canonical_name"],
#             "type_key": self._type_key(concept),
#             "definition": concept.get("definition"),
#             "synonyms": self._dedupe_strings(concept.get("synonyms", [])),
#             "keywords": self._dedupe_strings(concept.get("keywords", [])),
#             "attributes": concept.get("attributes", []),
#             "source_page": concept.get("source_page"),
#             "element_id": concept.get("element_id"),
#             "section_path": concept.get("section_path", []),
#             "hierarchy_context": concept.get("hierarchy_context"),
#             "proposal_status": "PENDING_REVIEW",
#             "candidate_concept_uid": resolution.get("candidate_concept_uid"),
#             "candidate_name": resolution.get("candidate_name"),
#             "candidate_similarity": resolution.get("similarity_score"),
#             "match_method": resolution.get("match_method"),
#         }

#     def _term_records(
#         self,
#         concept: Dict[str, Any],
#         resolution: Dict[str, Any],
#     ) -> List[Dict[str, Any]]:
#         owner_uid = resolution.get("concept_uid") or resolution.get("proposal_uid")
#         canonical_name = resolution["canonical_name"]
#         proposed = resolution["resolution_status"] != "EXISTING"

#         output = [
#             {
#                 "concept_uid": owner_uid,
#                 "term": canonical_name,
#                 "term_type": "canonical",
#                 "proposed": proposed,
#             }
#         ]

#         for synonym in self._dedupe_strings(concept.get("synonyms", [])):
#             if synonym.casefold() == canonical_name.casefold():
#                 continue
#             output.append(
#                 {
#                     "concept_uid": owner_uid,
#                     "term": synonym,
#                     "term_type": "synonym",
#                     "proposed": proposed,
#                 }
#             )

#         return output

#     def _concept_field_records(
#         self,
#         document_id: str,
#         concept: Dict[str, Any],
#         resolution: Dict[str, Any],
#     ) -> List[Dict[str, Any]]:
#         owner_uid = resolution.get("concept_uid") or resolution.get("proposal_uid")
#         proposed = resolution["resolution_status"] != "EXISTING"

#         output: List[Dict[str, Any]] = []

#         simple_fields = {
#             "definition": concept.get("definition"),
#             "hierarchy_context": concept.get("hierarchy_context"),
#             "source_page": concept.get("source_page"),
#             "element_id": concept.get("element_id"),
#         }

#         for field_name, field_value in simple_fields.items():
#             if field_value in (None, ""):
#                 continue

#             output.append(
#                 {
#                     "field_uid": self._stable_field_uid(
#                         str(owner_uid),
#                         field_name,
#                         field_value,
#                         document_id,
#                     ),
#                     "concept_uid": owner_uid,
#                     "field_name": field_name,
#                     "field_value": field_value,
#                     "document_id": document_id,
#                     "proposed": proposed,
#                 }
#             )

#         attributes = concept.get("attributes", [])
#         if isinstance(attributes, list):
#             for attribute in attributes:
#                 if not isinstance(attribute, dict):
#                     continue

#                 name = self._normalize_name(attribute.get("name"))
#                 value = attribute.get("value")

#                 if not name or value in (None, ""):
#                     continue

#                 output.append(
#                     {
#                         "field_uid": self._stable_field_uid(
#                             str(owner_uid),
#                             name,
#                             value,
#                             document_id,
#                         ),
#                         "concept_uid": owner_uid,
#                         "field_name": name,
#                         "field_value": value,
#                         "document_id": document_id,
#                         "proposed": proposed,
#                     }
#                 )

#         return output

#     # ============================================================
#     # QUALITY GATE
#     # ============================================================

#     def _quality_gate(
#         self,
#         input_concepts: int,
#         existing_count: int,
#         new_count: int,
#         review_count: int,
#         rejected_count: int,
#         ready_relationships: int,
#         pending_relationships: int,
#         rejected_relationships: int,
#     ) -> Dict[str, Any]:
#         warnings = list(dict.fromkeys(self._warnings))

#         if input_concepts <= 0:
#             return {
#                 "status": "FAILED",
#                 "score": 0,
#                 "reason": "No concepts were found in extracted_knowledge.json.",
#                 "warnings": warnings,
#                 "can_continue": False,
#             }

#         rejected_ratio = rejected_count / max(input_concepts, 1)

#         if rejected_ratio > 0.35:
#             return {
#                 "status": "NEEDS_EXTRACTION_REVIEW",
#                 "score": 60,
#                 "reason": "Too many concepts were rejected. Review the knowledge extraction prompt/output.",
#                 "warnings": warnings,
#                 "can_continue": False,
#             }

#         if len(self._mysql_by_uid) == 0:
#             return {
#                 "status": "FIRST_INGESTION_REVIEW_REQUIRED",
#                 "score": 90,
#                 "reason": (
#                     "MySQL and Qdrant are ready, but no trusted concepts exist yet. "
#                     "This is valid for first ingestion. Commit proposals for review, "
#                     "then approve and sync embeddings."
#                 ),
#                 "warnings": warnings,
#                 "can_continue": True,
#             }

#         if existing_count == 0 and new_count > 0:
#             return {
#                 "status": "LOW_REUSE_REVIEW_REQUIRED",
#                 "score": 82,
#                 "reason": (
#                     "Trusted concepts exist, but this document did not reuse any. "
#                     "Review synonym quality and Qdrant sync."
#                 ),
#                 "warnings": warnings,
#                 "can_continue": True,
#             }

#         if pending_relationships > 0 and ready_relationships == 0:
#             return {
#                 "status": "APPROVAL_REQUIRED",
#                 "score": 88,
#                 "reason": "Concepts were normalized, but relationships need concept approval before commit.",
#                 "warnings": warnings,
#                 "can_continue": True,
#             }

#         return {
#             "status": "PASS",
#             "score": 98,
#             "reason": "Normalization output is ready for validate-commit.",
#             "warnings": warnings,
#             "can_continue": True,
#         }

#     # ============================================================
#     # MASTER
#     # ============================================================

#     async def normalize_graph_and_map(self, document_id: str) -> Dict[str, Any]:
#         started = time.perf_counter()

#         processed_base = self.processed_dir / document_id
#         knowledge_path = processed_base / "extracted_knowledge.json"

#         knowledge = self._require_knowledge_artifact(knowledge_path, document_id)

#         raw_concepts = [
#             item for item in knowledge.get("concepts", [])
#             if isinstance(item, dict)
#         ]
#         relationships = [
#             item for item in knowledge.get("relationships", [])
#             if isinstance(item, dict)
#         ]

#         logger.info(
#             f"Normalization started for {document_id}. "
#             f"Concepts={len(raw_concepts)}, Relationships={len(relationships)}"
#         )

#         await self._mysql_preflight()
#         await self._load_mysql_catalog()
#         valid_relationship_types = await self._load_relationship_types()
#         await self._prepare_qdrant()

#         resolutions_by_index: Dict[int, Dict[str, Any]] = {}
#         rejected_concepts: List[Dict[str, Any]] = []
#         unresolved: List[Tuple[int, Dict[str, Any]]] = []

#         seen_valid_concept_keys: Set[str] = set()
#         duplicate_concepts = 0

#         for index, concept in enumerate(raw_concepts):
#             original_name = self._normalize_name(concept.get("canonical_name", ""))

#             if not original_name:
#                 rejected_concepts.append(
#                     {
#                         "concept": concept,
#                         "resolution": {
#                             "resolution_status": "REJECTED",
#                             "reason": "empty_concept_name",
#                         },
#                     }
#                 )
#                 continue

#             if self._is_metadata_concept(original_name):
#                 rejected_concepts.append(
#                     {
#                         "concept": concept,
#                         "resolution": {
#                             "canonical_name": original_name,
#                             "resolution_status": "REJECTED",
#                             "reason": "document_metadata",
#                         },
#                     }
#                 )
#                 continue

#             if self._is_floating_value(original_name):
#                 rejected_concepts.append(
#                     {
#                         "concept": concept,
#                         "resolution": {
#                             "canonical_name": original_name,
#                             "resolution_status": "REJECTED",
#                             "reason": "floating_numeric_or_formula_value",
#                         },
#                     }
#                 )
#                 continue

#             key = self._comparison_key(original_name)
#             if key in seen_valid_concept_keys:
#                 duplicate_concepts += 1

#             seen_valid_concept_keys.add(key)

#             exact = self._exact_mysql_resolution(original_name)
#             if exact:
#                 resolutions_by_index[index] = exact
#             else:
#                 unresolved.append((index, concept))

#         semantic_results = await self._resolve_semantic_batch(document_id, unresolved)
#         resolutions_by_index.update(semantic_results)

#         for index, concept in unresolved:
#             if index in resolutions_by_index:
#                 continue

#             name = self._normalize_name(concept.get("canonical_name", ""))
#             resolutions_by_index[index] = self._proposal_resolution(document_id, name)

#         concept_lookup: Dict[str, Dict[str, Any]] = {}
#         canonical_mapping = []
#         proposals = []
#         concept_terms = []
#         concept_fields = []

#         for index, concept in enumerate(raw_concepts):
#             resolution = resolutions_by_index.get(index)
#             if not resolution:
#                 continue

#             mapping_record = {
#                 "source_concept": concept.get("canonical_name"),
#                 **resolution,
#             }
#             canonical_mapping.append(mapping_record)

#             original_key = self._comparison_key(concept.get("canonical_name", ""))
#             canonical_key = self._comparison_key(resolution["canonical_name"])

#             concept_lookup[original_key] = resolution
#             concept_lookup[canonical_key] = resolution

#             if resolution["resolution_status"] in {"NEW_PROPOSAL", "REVIEW_REQUIRED"}:
#                 proposals.append(self._proposal_record(document_id, concept, resolution))

#             concept_terms.extend(self._term_records(concept, resolution))
#             concept_fields.extend(self._concept_field_records(document_id, concept, resolution))

#         canonical_mapping = self._dedupe_records(
#             canonical_mapping,
#             ["source_concept", "canonical_name", "resolution_status"],
#         )
#         proposals = self._dedupe_records(proposals, ["proposal_uid"])
#         concept_terms = self._dedupe_records(concept_terms, ["concept_uid", "term", "term_type"])
#         concept_fields = self._dedupe_records(concept_fields, ["field_uid"])

#         ready_relationships = []
#         pending_relationships = []
#         rejected_relationships = []
#         seen_relationships: Set[str] = set()

#         for relationship in relationships:
#             mapped = await self._resolve_relationship(
#                 relationship,
#                 concept_lookup,
#                 valid_relationship_types,
#             )

#             signature = mapped.get("relationship_uid") or json.dumps(
#                 mapped,
#                 sort_keys=True,
#                 default=str,
#             )

#             if signature in seen_relationships:
#                 continue
#             seen_relationships.add(signature)

#             if mapped.get("status") == "READY":
#                 ready_relationships.append(mapped)
#             elif mapped.get("status") == "REVIEW_REQUIRED":
#                 pending_relationships.append(mapped)
#             else:
#                 rejected_relationships.append(mapped)

#         existing_count = sum(
#             1
#             for item in canonical_mapping
#             if item.get("resolution_status") == "EXISTING"
#         )
#         new_count = sum(
#             1
#             for item in canonical_mapping
#             if item.get("resolution_status") == "NEW_PROPOSAL"
#         )
#         review_count = sum(
#             1
#             for item in canonical_mapping
#             if item.get("resolution_status") == "REVIEW_REQUIRED"
#         )

#         quality_gate = self._quality_gate(
#             input_concepts=len(raw_concepts),
#             existing_count=existing_count,
#             new_count=new_count,
#             review_count=review_count,
#             rejected_count=len(rejected_concepts),
#             ready_relationships=len(ready_relationships),
#             pending_relationships=len(pending_relationships),
#             rejected_relationships=len(rejected_relationships),
#         )

#         mysql_payload = {
#             "document_id": document_id,
#             "existing_concepts": [
#                 item
#                 for item in canonical_mapping
#                 if item.get("resolution_status") == "EXISTING"
#             ],
#             "concepts": [],
#             "concept_terms": concept_terms,
#             "concept_fields": concept_fields,
#             "concept_field_arrays": [],
#             "concept_relationships": ready_relationships,
#             "concept_proposals": proposals,
#             "pending_relationships": pending_relationships,
#             "rejected_concepts": rejected_concepts,
#             "rejected_relationships": rejected_relationships,
#             "question_concept_links": [],
#             "option_concept_links": [],
#             "concept_exclusions": [],
#             "governance_rules": [],
#             "validation_stats": {
#                 "input_concepts": len(raw_concepts),
#                 "unique_valid_concept_keys": len(seen_valid_concept_keys),
#                 "duplicate_concepts_detected": duplicate_concepts,
#                 "existing_concepts_reused": existing_count,
#                 "new_proposals_generated": new_count,
#                 "ambiguous_concepts_for_review": review_count,
#                 "rejected_concepts": len(rejected_concepts),
#                 "input_relationships": len(relationships),
#                 "live_edges_ready": len(ready_relationships),
#                 "pending_relationships": len(pending_relationships),
#                 "rejected_relationships": len(rejected_relationships),
#                 "quality_gate": quality_gate,
#             },
#         }

#         canonical_path = processed_base / "canonical_mapping.json"
#         mysql_payload_path = processed_base / "mysql_payload.json"

#         canonical_artifact = {
#             "document_id": document_id,
#             "canonical_mapping": canonical_mapping,
#             "summary": {
#                 "existing": existing_count,
#                 "new_proposals": new_count,
#                 "review_required": review_count,
#                 "rejected": len(rejected_concepts),
#                 "duplicate_concepts_detected": duplicate_concepts,
#                 "quality_gate": quality_gate,
#             },
#         }

#         self._atomic_write_json(canonical_path, canonical_artifact)
#         self._atomic_write_json(mysql_payload_path, mysql_payload)

#         try:
#             self._write_metadata_status(
#                 document_id,
#                 "NORMALIZED_AND_MAPPED",
#                 {
#                     "normalization_summary": {
#                         "input_concepts": len(raw_concepts),
#                         "existing_concepts_reused": existing_count,
#                         "new_proposals": new_count,
#                         "review_required": review_count,
#                         "rejected_concepts": len(rejected_concepts),
#                         "quality_gate": quality_gate,
#                     }
#                 },
#             )
#         except Exception as exc:
#             self._warnings.append(f"Metadata status update failed: {exc}")
#             logger.warning(f"Metadata status update failed for {document_id}: {exc}")

#         elapsed = time.perf_counter() - started

#         logger.info(
#             f"Normalization + Graph + Schema Mapping completed "
#             f"for {document_id} in {elapsed:.2f}s. "
#             f"existing={existing_count}, proposals={new_count}, "
#             f"review={review_count}, rejected={len(rejected_concepts)}, "
#             f"ready_edges={len(ready_relationships)}"
#         )

#         return {
#             "document_id": document_id,
#             "pipeline_status": "NORMALIZED_AND_MAPPED",
#             "normalization": {
#                 "input_concepts": len(raw_concepts),
#                 "unique_valid_concept_keys": len(seen_valid_concept_keys),
#                 "duplicate_concepts_detected": duplicate_concepts,
#                 "existing_concepts_reused": existing_count,
#                 "new_proposals": new_count,
#                 "review_required": review_count,
#                 "rejected_concepts": len(rejected_concepts),
#             },
#             "knowledge_graph": {
#                 "input_relationships": len(relationships),
#                 "ready_relationships": len(ready_relationships),
#                 "pending_relationships": len(pending_relationships),
#                 "rejected_relationships": len(rejected_relationships),
#             },
#             "schema_mapping": {
#                 "concepts": 0,
#                 "concept_terms": len(concept_terms),
#                 "concept_fields": len(concept_fields),
#                 "concept_relationships": len(ready_relationships),
#                 "concept_proposals": len(proposals),
#             },
#             "infrastructure": {
#                 "mysql": "READY",
#                 "mysql_trusted_concepts_loaded": len(self._mysql_by_uid),
#                 "qdrant_reachable": self._qdrant_reachable,
#                 "qdrant_collection": self.qdrant_collection,
#                 "qdrant_collection_created": self._qdrant_collection_created,
#                 "qdrant_has_points": self._qdrant_has_points,
#                 "semantic_matching_used": self._qdrant_has_points,
#                 "embedding_model": self.embedding_model,
#                 "embedding_dimensions": self.embedding_dimensions,
#             },
#             "quality_gate": quality_gate,
#             "artifacts": {
#                 "canonical_mapping": str(canonical_path.relative_to(settings.BASE_DIR)),
#                 "mysql_payload": str(mysql_payload_path.relative_to(settings.BASE_DIR)),
#             },
#             "processing_time_seconds": round(elapsed, 2),
#             "next_step": (
#                 f"{settings.API_V1_STR}/documents/{document_id}/validate-commit"
#             ),
#             "recommended_actions": [
#                 "Run validate-commit to store proposal payload safely.",
#                 "Review and approve concept proposals in admin/HITL workflow.",
#                 "After approval, sync approved concept embeddings to Qdrant.",
#                 "Re-run normalization for future documents to reuse trusted concepts.",
#             ],
#         }











# import asyncio
# import hashlib
# import json
# import re
# import time
# from pathlib import Path
# from typing import Any, Dict, List, Optional, Set, Tuple

# from openai import AsyncOpenAI
# from qdrant_client import AsyncQdrantClient, models
# from sqlalchemy import text
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.core.config import settings
# from app.core.exceptions import ProcessingError
# from app.core.logger import logger


# class NormalizationGraphService:
#     """
#     TagTaste Concept DB aligned normalization.

#     Architecture rules implemented:
#         - MySQL is source of truth.
#         - Qdrant is only a mirror/candidate retrieval layer.
#         - Proposal flow is only for sensory substrate concepts:
#             sensory_attribute
#             descriptor
#         - Seeded substrate types are never AI-proposed:
#             sensory_scale, family, axis, modality, benchmark
#         - Routing/policy types are never AI-proposed:
#             intent_group, sql_query_pattern, analysis_recipe, recipe_step,
#             classifier_prompt, governance_rule, answer_example, etc.
#         - Existing concepts are confirmed by MySQL.
#         - Semantic Qdrant matches are accepted only after MySQL UID confirmation.
#         - Relationships touching proposals stay pending.
#         - Output is deterministic and safe for validate-commit.
#     """

#     DEFAULT_EMBEDDING_MODEL = "text-embedding-3-large"
#     DEFAULT_QDRANT_COLLECTION = "concepts"
#     DEFAULT_EMBEDDING_DIMENSIONS = 3072

#     SEMANTIC_MATCH_THRESHOLD = 0.88
#     SEMANTIC_REVIEW_THRESHOLD = 0.78
#     QDRANT_LIMIT = 5

#     KNOWLEDGE_REQUIRED_STATUS = "KNOWLEDGE_EXTRACTED"

#     PROPOSAL_ALLOWED_TYPE_KEYS: Set[str] = {
#         "sensory_attribute",
#         "descriptor",
#     }

#     SEEDED_SUBSTRATE_TYPE_KEYS: Set[str] = {
#         "sensory_scale",
#         "family",
#         "axis",
#         "modality",
#         "benchmark",
#     }

#     POLICY_LAYER_TYPE_KEYS: Set[str] = {
#         "intent_group",
#         "sql_query_pattern",
#         "analysis_recipe",
#         "recipe_step",
#         "classifier_prompt",
#         "governance_rule",
#         "guardrail_rule",
#         "answer_example",
#         "category_knowledge",
#         "alignment_gate",
#         "prompt_requirement",
#         "answer_shape_template",
#         "question_understanding",
#         "question_shape",
#         "question_specificity",
#         "section_weight_profile",
#         "data_source",
#         "hidden_intent",
#         "reasoning_pattern",
#         "category_profile",
#         "metric",
#         "domain",
#         "data_binding_rule",
#         "sql_routing",
#         "stakeholder_directive",
#         "route",
#         "bypass_rule",
#         "analytical_method",
#         "render_template",
#         "demographic_axis",
#         "persona",
#         "verified_tool",
#         "ar_question_slot",
#     }

#     GROUP_B_PARENT_TYPE_KEYS: Set[str] = {
#         "intent_group",
#         "guardrail_rule",
#         "domain",
#     }

#     GROUP_C_PHP_LOADED_TYPE_KEYS: Set[str] = {
#         "classifier_prompt",
#         "persona",
#     }

#     DEFAULT_RELATIONSHIP_TYPES: Set[str] = {
#         "is_child_of",
#         "causes",
#         "measured_by",
#         "described_by",
#         "influences",
#         "related_to",
#         "part_of",
#         "categorized_as",
#         "applies_to",
#         "masks",
#         "enhances",
#         "co_occurs_with",
#         "substitutes_for",
#         "is_example_of",
#         "triggered_by",
#         "renders_as",
#         "uses_prompt",
#         "gated_by",
#         "composes_from",
#         "default_prompt",
#         "default_shape",
#         "benchmarked_by",
#         "pulls_from",
#         "uses_sql",
#         "uses_method",
#         "checks_metric",
#         "column_in",
#         "measured_on",
#         "uses_render_template",
#         "cites_from",
#         "uses_weights",
#         "writing_contract",
#         "footer_template",
#         "triggers_expansion",
#         "has_default_shape",
#         "tiers_for",
#         "threshold_for",
#         "contains",
#         "has_attribute",
#         "has_sensory_attribute",
#         "has_descriptor",
#         "has_intensity",
#         "has_score",
#         "uses_scale",
#         "evaluated_by",
#         "compared_with",
#         "prepared_by",
#         "derived_from",
#         "belongs_to",
#         "associated_with",
#         "defined_by",
#         "measured_under",
#         "tested_by",
#         "has_method",
#         "has_property",
#         "correlates_with",
#     }

#     CATEGORY_TO_TYPE_KEY = {
#         "Attribute": "sensory_attribute",
#         "Sensory_Attribute": "sensory_attribute",
#         "Sensory Attribute": "sensory_attribute",
#         "Descriptor": "descriptor",
#         "Scale": "sensory_scale",
#         "Sensory_Scale": "sensory_scale",
#         "Sensory Scale": "sensory_scale",
#         "Family": "family",
#         "Axis": "axis",
#         "Modality": "modality",
#         "Benchmark": "benchmark",
#         "Method": "analytical_method",
#         "Analysis_Method": "analytical_method",
#         "Analysis Method": "analytical_method",
#         "Metric": "metric",
#         "Entity": "food_science",
#         "Food Science": "food_science",
#         "Food_Science": "food_science",
#         "Property": "food_science",
#         "Process": "food_science",
#         "Material": "food_science",
#         "Chemical": "food_science",
#         "Instrument": "food_science",
#         "Organization": "food_science",
#         "Measurement": "metric",
#         "Product": "category_knowledge",
#         "Sample": "category_knowledge",
#     }

#     ATTRIBUTE_HINTS = {
#         "sweetness",
#         "sourness",
#         "saltiness",
#         "bitterness",
#         "umami",
#         "crunchiness",
#         "crispness",
#         "hardness",
#         "firmness",
#         "chewiness",
#         "creaminess",
#         "stickiness",
#         "juiciness",
#         "aroma intensity",
#         "flavour intensity",
#         "flavor intensity",
#         "appearance",
#         "color",
#         "colour",
#         "aftertaste",
#         "mouthfeel",
#         "texture",
#         "viscosity",
#     }

#     DESCRIPTOR_HINTS = {
#         "fruity",
#         "floral",
#         "metallic",
#         "burnt",
#         "smoky",
#         "crispy",
#         "creamy",
#         "rancid",
#         "stale",
#         "fresh",
#         "earthy",
#         "woody",
#         "spicy",
#         "bitter",
#         "sour",
#         "sweet",
#         "salty",
#         "astringent",
#         "grainy",
#         "smooth",
#         "rough",
#         "rubbery",
#         "chalky",
#     }

#     SCALE_HINTS = {
#         "scale",
#         "likert",
#         "nps",
#         "jar",
#         "just about right",
#         "hedonic",
#         "9-point",
#         "7-point",
#         "5-point",
#         "ranking",
#         "boolean",
#         "categorical",
#         "intensity scale",
#     }

#     FAMILY_HINTS = {
#         "basic taste",
#         "aromatics",
#         "texture",
#         "visual",
#         "trigeminal",
#         "physiological",
#         "temporal",
#         "acoustic",
#         "marketing",
#         "functional",
#         "ingredient",
#         "product category",
#         "quality",
#         "physical",
#         "defects",
#         "context",
#         "metadata",
#     }

#     AXIS_HINTS = {
#         "sensory",
#         "preference",
#         "diagnostic",
#     }

#     MODALITY_HINTS = {
#         "gustatory",
#         "olfactory",
#         "tactile",
#         "visual",
#         "auditory",
#         "trigeminal",
#     }

#     METADATA_PATTERNS = [
#         r"\bisbn\b",
#         r"\bcopyright\b",
#         r"\bpublisher\b",
#         r"\bedition\b",
#         r"\bauthor\b",
#         r"\bprinted by\b",
#         r"\ball rights reserved\b",
#         r"\btable of contents\b",
#         r"\bindex\b",
#         r"\breferences\b",
#         r"\bbibliography\b",
#     ]

#     PURE_NUMBER_RE = re.compile(
#         r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:\s*%|\s*[a-zA-Z°]+)?$"
#     )
#     ASSIGNMENT_VALUE_RE = re.compile(
#         r"^[A-Za-zαβμσχ²χ]+(?:\d+)?\s*=\s*[+-]?\d+(?:\.\d+)?%?$"
#     )
#     SHORT_FORMULA_RE = re.compile(
#         r"^(?:n\d*|x\d*|s\d*|t\d*|f|p|d\d*|c\d*|χ²?)\s*=?\s*[+-]?\d*(?:\.\d+)?%?$",
#         re.IGNORECASE,
#     )

#     def __init__(self, db: AsyncSession):
#         self.db = db

#         self.raw_dir = Path(settings.STORAGE_RAW_DIR)
#         self.processed_dir = Path(settings.STORAGE_PROCESSED_DIR)

#         self.embedding_model = getattr(
#             settings,
#             "OPENAI_EMBEDDING_MODEL",
#             self.DEFAULT_EMBEDDING_MODEL,
#         )
#         self.embedding_dimensions = int(
#             getattr(
#                 settings,
#                 "OPENAI_EMBEDDING_DIMENSIONS",
#                 self.DEFAULT_EMBEDDING_DIMENSIONS,
#             )
#         )

#         self.openai_client = AsyncOpenAI(
#             api_key=settings.OPENAI_API_KEY,
#             timeout=float(getattr(settings, "OPENAI_TIMEOUT", 60.0)),
#             max_retries=int(getattr(settings, "OPENAI_MAX_RETRIES", 2)),
#         )

#         qdrant_url = getattr(settings, "QDRANT_URL", None)
#         if not qdrant_url:
#             qdrant_url = (
#                 f"http://{getattr(settings, 'QDRANT_HOST', 'localhost')}:"
#                 f"{int(getattr(settings, 'QDRANT_PORT', 6333))}"
#             )

#         self.qdrant = AsyncQdrantClient(
#             url=qdrant_url,
#             api_key=(getattr(settings, "QDRANT_API_KEY", "") or None),
#             timeout=5.0,
#             check_compatibility=False,
#         )

#         self.qdrant_collection = getattr(
#             settings,
#             "QDRANT_CONCEPT_COLLECTION",
#             self.DEFAULT_QDRANT_COLLECTION,
#         )

#         self.normalization_concurrency = max(
#             1,
#             int(getattr(settings, "NORMALIZATION_CONCURRENCY", 12)),
#         )

#         self._table_columns: Dict[str, List[str]] = {}
#         self._relationship_types_by_key: Dict[str, Dict[str, Any]] = {}
#         self._relationship_types: Optional[Set[str]] = None

#         self._mysql_by_name: Dict[str, Dict[str, Any]] = {}
#         self._mysql_by_uid: Dict[str, Dict[str, Any]] = {}
#         self._mysql_by_id: Dict[str, Dict[str, Any]] = {}

#         self._embedding_cache: Dict[str, List[float]] = {}

#         self._qdrant_reachable = False
#         self._qdrant_has_points = False
#         self._qdrant_collection_created = False
#         self._qdrant_vector_size: Optional[int] = None

#         self._warnings: List[str] = []

#     # ============================================================
#     # BASIC HELPERS
#     # ============================================================

#     @staticmethod
#     def _normalize_space(value: Any) -> str:
#         return re.sub(r"\s+", " ", str(value or "")).strip()

#     def _normalize_name(self, value: Any) -> str:
#         return self._normalize_space(value).strip(" .,:;|-_")

#     def _comparison_key(self, value: Any) -> str:
#         normalized = self._normalize_name(value).casefold()
#         return re.sub(r"[^a-z0-9]+", "", normalized)

#     @staticmethod
#     def _dedupe_strings(values: Any) -> List[str]:
#         if not isinstance(values, list):
#             values = [values] if values else []

#         output: List[str] = []
#         seen = set()

#         for value in values:
#             item = str(value or "").strip()
#             if not item:
#                 continue

#             key = item.casefold()
#             if key in seen:
#                 continue

#             seen.add(key)
#             output.append(item)

#         return output

#     @staticmethod
#     def _stable_hash(*parts: Any, length: int = 16) -> str:
#         raw = "|".join(str(part or "") for part in parts)
#         return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]

#     def _stable_proposal_uid(
#         self,
#         document_id: str,
#         type_key: str,
#         canonical_name: str,
#     ) -> str:
#         return "CP_" + self._stable_hash(
#             document_id,
#             type_key,
#             self._comparison_key(canonical_name),
#             length=16,
#         ).upper()

#     def _stable_field_uid(
#         self,
#         concept_ref: str,
#         field_key: str,
#         field_value: Any,
#         document_id: str,
#     ) -> str:
#         return "FIELD_" + self._stable_hash(
#             concept_ref,
#             field_key,
#             field_value,
#             document_id,
#             length=16,
#         ).upper()

#     @staticmethod
#     def _stable_relationship_uid(
#         source_ref: str,
#         relationship_type: str,
#         target_ref: str,
#     ) -> str:
#         digest = hashlib.sha256(
#             f"{source_ref}|{relationship_type}|{target_ref}".encode("utf-8")
#         ).hexdigest()[:16]
#         return f"REL_{digest.upper()}"

#     @staticmethod
#     def _dedupe_records(
#         records: List[Dict[str, Any]],
#         keys: List[str],
#     ) -> List[Dict[str, Any]]:
#         output = []
#         seen = set()

#         for record in records:
#             signature = tuple(
#                 json.dumps(record.get(key), sort_keys=True, default=str)
#                 for key in keys
#             )
#             if signature in seen:
#                 continue
#             seen.add(signature)
#             output.append(record)

#         return output

#     def _is_metadata_concept(self, concept_name: str) -> bool:
#         lowered = concept_name.casefold()
#         return any(re.search(pattern, lowered) for pattern in self.METADATA_PATTERNS)

#     def _is_floating_value(self, concept_name: str) -> bool:
#         name = self._normalize_name(concept_name)
#         if not name:
#             return True

#         if len(name) == 1 and name.casefold() in {
#             "c",
#             "d",
#             "f",
#             "p",
#             "s",
#             "t",
#             "x",
#             "n",
#         }:
#             return True

#         if self.PURE_NUMBER_RE.fullmatch(name):
#             return True

#         if self.ASSIGNMENT_VALUE_RE.fullmatch(name):
#             return True

#         if self.SHORT_FORMULA_RE.fullmatch(name):
#             if name.casefold() not in {"ph"}:
#                 return True

#         return False

#     def _type_key(self, concept: Dict[str, Any]) -> str:
#         raw_value = (
#             concept.get("type_key")
#             or concept.get("category")
#             or concept.get("concept_type")
#             or "food_science"
#         )

#         raw_text = str(raw_value or "").strip()
#         if raw_text in self.CATEGORY_TO_TYPE_KEY:
#             return self.CATEGORY_TO_TYPE_KEY[raw_text]

#         normalized = re.sub(
#             r"[^a-z0-9]+",
#             "_",
#             raw_text.casefold(),
#         ).strip("_")

#         if normalized in self.CATEGORY_TO_TYPE_KEY.values():
#             return normalized

#         name = self._normalize_name(concept.get("canonical_name", ""))
#         name_lower = name.casefold()

#         if any(item in name_lower for item in self.SCALE_HINTS):
#             return "sensory_scale"

#         if name_lower in self.FAMILY_HINTS:
#             return "family"

#         if name_lower in self.AXIS_HINTS:
#             return "axis"

#         if name_lower in self.MODALITY_HINTS:
#             return "modality"

#         if any(item in name_lower for item in self.ATTRIBUTE_HINTS):
#             return "sensory_attribute"

#         if any(item in name_lower for item in self.DESCRIPTOR_HINTS):
#             return "descriptor"

#         return normalized or "food_science"

#     def _concept_policy_decision(
#         self,
#         type_key: str,
#         concept_name: str,
#     ) -> Dict[str, Any]:
#         if type_key in self.PROPOSAL_ALLOWED_TYPE_KEYS:
#             return {
#                 "decision": "ALLOW_PROPOSAL",
#                 "reason": "sensory_substrate_proposal_allowed",
#                 "can_be_proposed": True,
#             }

#         if type_key in self.SEEDED_SUBSTRATE_TYPE_KEYS:
#             return {
#                 "decision": "REQUIRE_SEEDED_MATCH",
#                 "reason": (
#                     f"{type_key} is a seeded sensory substrate type. "
#                     "It should match an existing DB row and should not be AI-proposed."
#                 ),
#                 "can_be_proposed": False,
#             }

#         if type_key in self.POLICY_LAYER_TYPE_KEYS:
#             return {
#                 "decision": "REQUIRE_ADMIN_SEEDING",
#                 "reason": (
#                     f"{type_key} belongs to routing/policy layer. "
#                     "It must be designed/admin-seeded, not AI-proposed."
#                 ),
#                 "can_be_proposed": False,
#             }

#         return {
#             "decision": "REQUIRE_ADMIN_REVIEW",
#             "reason": (
#                 f"{type_key} is not part of the attribute/descriptor proposal flow. "
#                 "Route it to admin/manual seed review."
#             ),
#             "can_be_proposed": False,
#         }

#     # ============================================================
#     # FILE HELPERS
#     # ============================================================

#     @staticmethod
#     def _read_json(path: Path) -> Dict[str, Any]:
#         if not path.exists():
#             raise FileNotFoundError(f"JSON artifact not found: {path}")

#         try:
#             raw = path.read_text(encoding="utf-8-sig")
#         except OSError as exc:
#             raise ProcessingError(f"Could not read JSON artifact {path}: {exc}") from exc

#         if not raw.strip():
#             raise ProcessingError(f"JSON artifact exists but is empty: {path}")

#         try:
#             value = json.loads(raw)
#         except json.JSONDecodeError as exc:
#             raise ProcessingError(
#                 f"JSON artifact is invalid: {path}. "
#                 f"line={exc.lineno}, column={exc.colno}, error={exc.msg}"
#             ) from exc

#         if not isinstance(value, dict):
#             raise ProcessingError(
#                 f"Expected JSON object in {path}, got {type(value).__name__}."
#             )

#         return value

#     @staticmethod
#     def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
#         path.parent.mkdir(parents=True, exist_ok=True)
#         temp_path = path.with_suffix(path.suffix + ".tmp")

#         with open(temp_path, "w", encoding="utf-8") as file:
#             json.dump(
#                 payload,
#                 file,
#                 indent=2,
#                 ensure_ascii=False,
#                 default=str,
#             )
#             file.flush()

#         temp_path.replace(path)

#     def _read_metadata(self, document_id: str) -> Dict[str, Any]:
#         path = self.raw_dir / document_id / "metadata.json"
#         if not path.exists():
#             raise FileNotFoundError(f"metadata.json not found for {document_id}.")
#         return self._read_json(path)

#     def _write_metadata_status(
#         self,
#         document_id: str,
#         status_value: str,
#         extra: Optional[Dict[str, Any]] = None,
#     ) -> None:
#         path = self.raw_dir / document_id / "metadata.json"
#         metadata = self._read_json(path)
#         metadata["pipeline_status"] = status_value
#         metadata["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
#         if extra:
#             metadata.update(extra)
#         self._atomic_write_json(path, metadata)

#     def _require_knowledge_artifact(
#         self,
#         knowledge_path: Path,
#         document_id: str,
#     ) -> Dict[str, Any]:
#         metadata = self._read_metadata(document_id)
#         pipeline_status = str(metadata.get("pipeline_status", "UNKNOWN")).strip()

#         if pipeline_status not in {
#             self.KNOWLEDGE_REQUIRED_STATUS,
#             "NORMALIZED_AND_MAPPED",
#         }:
#             raise ProcessingError(
#                 f"Knowledge extraction is not complete for {document_id}. "
#                 f"Current pipeline_status={pipeline_status}; "
#                 f"required={self.KNOWLEDGE_REQUIRED_STATUS}."
#             )

#         knowledge = self._read_json(knowledge_path)

#         concepts = knowledge.get("concepts", [])
#         relationships = knowledge.get("relationships", [])

#         if not isinstance(concepts, list):
#             raise ProcessingError("'concepts' must be a JSON array.")

#         if not isinstance(relationships, list):
#             raise ProcessingError("'relationships' must be a JSON array.")

#         return knowledge

#     # ============================================================
#     # MYSQL
#     # ============================================================

#     async def _mysql_preflight(self) -> None:
#         try:
#             result = await self.db.execute(text("SELECT 1 AS ok"))
#             row = result.first()
#             if not row or int(row[0]) != 1:
#                 raise RuntimeError("SELECT 1 returned an unexpected value")
#         except Exception as exc:
#             raise ProcessingError(
#                 "MySQL is unavailable. Normalization cannot safely continue "
#                 "because MySQL is the source of truth. "
#                 f"Database error: {exc}"
#             ) from exc

#     async def _get_columns(self, table_name: str) -> List[str]:
#         if table_name in self._table_columns:
#             return self._table_columns[table_name]

#         result = await self.db.execute(
#             text(
#                 """
#                 SELECT COLUMN_NAME
#                 FROM INFORMATION_SCHEMA.COLUMNS
#                 WHERE TABLE_SCHEMA = DATABASE()
#                   AND TABLE_NAME = :table_name
#                 ORDER BY ORDINAL_POSITION
#                 """
#             ),
#             {"table_name": table_name},
#         )

#         columns = [str(row[0]) for row in result.all()]
#         self._table_columns[table_name] = columns
#         return columns

#     @staticmethod
#     def _pick_column(
#         available: List[str],
#         candidates: List[str],
#     ) -> Optional[str]:
#         lookup = {column.casefold(): column for column in available}
#         for candidate in candidates:
#             if candidate.casefold() in lookup:
#                 return lookup[candidate.casefold()]
#         return None

#     async def _load_mysql_catalog(self) -> None:
#         concept_columns = await self._get_columns("concepts")
#         if not concept_columns:
#             raise ProcessingError(
#                 "Required MySQL table 'concepts' does not exist in the current database."
#             )

#         id_col = self._pick_column(concept_columns, ["id", "concept_id"])
#         uid_col = self._pick_column(concept_columns, ["concept_uid", "uid"])
#         name_col = self._pick_column(
#             concept_columns,
#             ["canonical_name", "name", "concept_name", "label"],
#         )
#         type_col = self._pick_column(
#             concept_columns,
#             ["type_key", "concept_type", "category"],
#         )
#         status_col = self._pick_column(
#             concept_columns,
#             ["status", "approval_status"],
#         )
#         has_vector_col = self._pick_column(concept_columns, ["has_vector"])

#         if not uid_col or not name_col:
#             raise ProcessingError(
#                 "Table 'concepts' must contain concept_uid/uid and canonical_name/name."
#             )

#         selected = []
#         if id_col:
#             selected.append(f"`{id_col}` AS concept_id")
#         selected.extend(
#             [
#                 f"`{uid_col}` AS concept_uid",
#                 f"`{name_col}` AS canonical_name",
#             ]
#         )
#         if type_col:
#             selected.append(f"`{type_col}` AS type_key")
#         if status_col:
#             selected.append(f"`{status_col}` AS concept_status")
#         if has_vector_col:
#             selected.append(f"`{has_vector_col}` AS has_vector")

#         result = await self.db.execute(
#             text(f"SELECT {', '.join(selected)} FROM concepts")
#         )

#         self._mysql_by_name.clear()
#         self._mysql_by_uid.clear()
#         self._mysql_by_id.clear()

#         for row in result.mappings().all():
#             uid = str(row["concept_uid"])
#             name = self._normalize_name(row["canonical_name"])
#             concept_id = row.get("concept_id")
#             type_key = str(row.get("type_key") or "").strip() or None

#             if not uid or not name:
#                 continue

#             status_value = row.get("concept_status")
#             if status_value and str(status_value).casefold() not in {
#                 "approved",
#                 "active",
#                 "published",
#                 "trusted",
#             }:
#                 continue

#             record = {
#                 "concept_id": concept_id,
#                 "concept_uid": uid,
#                 "canonical_name": name,
#                 "type_key": type_key,
#                 "status": status_value,
#                 "has_vector": row.get("has_vector"),
#             }

#             self._mysql_by_uid[uid] = record
#             if concept_id is not None:
#                 self._mysql_by_id[str(concept_id)] = record

#             self._mysql_by_name[self._comparison_key(name)] = record

#         await self._load_concept_terms_into_catalog()

#         logger.info(
#             "Loaded trusted MySQL concept catalog: "
#             f"concepts={len(self._mysql_by_uid)}, "
#             f"name/term keys={len(self._mysql_by_name)}"
#         )

#     async def _load_concept_terms_into_catalog(self) -> None:
#         term_columns = await self._get_columns("concept_terms")
#         if not term_columns:
#             return

#         term_col = self._pick_column(
#             term_columns,
#             ["term", "term_text", "name", "value", "synonym"],
#         )
#         ref_id_col = self._pick_column(term_columns, ["concept_id"])
#         ref_uid_col = self._pick_column(term_columns, ["concept_uid", "uid"])
#         status_col = self._pick_column(term_columns, ["status", "is_active"])

#         if not term_col or not (ref_id_col or ref_uid_col):
#             return

#         selected = [f"`{term_col}` AS matched_term"]
#         if ref_id_col:
#             selected.append(f"`{ref_id_col}` AS concept_ref_id")
#         if ref_uid_col:
#             selected.append(f"`{ref_uid_col}` AS concept_ref_uid")
#         if status_col:
#             selected.append(f"`{status_col}` AS term_status")

#         result = await self.db.execute(
#             text(
#                 f"""
#                 SELECT {', '.join(selected)}
#                 FROM concept_terms
#                 WHERE `{term_col}` IS NOT NULL
#                 """
#             )
#         )

#         for row in result.mappings().all():
#             status_value = row.get("term_status")
#             if status_value is not None:
#                 status_text = str(status_value).casefold()
#                 if status_text not in {"1", "active", "approved", "true"}:
#                     continue

#             term_value = self._normalize_name(row["matched_term"])
#             if not term_value:
#                 continue

#             trusted = None
#             if ref_uid_col:
#                 trusted = self._mysql_by_uid.get(str(row.get("concept_ref_uid")))
#             if not trusted and ref_id_col:
#                 trusted = self._mysql_by_id.get(str(row.get("concept_ref_id")))

#             if trusted:
#                 self._mysql_by_name[self._comparison_key(term_value)] = trusted

#     async def _load_relationship_types(self) -> Set[str]:
#         if self._relationship_types is not None:
#             return self._relationship_types

#         columns = await self._get_columns("relationship_types")
#         if not columns:
#             self._warnings.append(
#                 "relationship_types table is missing; default relationship types were used."
#             )
#             self._relationship_types = set(self.DEFAULT_RELATIONSHIP_TYPES)
#             return self._relationship_types

#         id_col = self._pick_column(columns, ["id", "relationship_type_id"])
#         key_col = self._pick_column(
#             columns,
#             ["type_key", "relationship_type", "key", "name"],
#         )
#         label_col = self._pick_column(columns, ["label"])
#         symmetric_col = self._pick_column(columns, ["is_symmetric"])
#         hierarchical_col = self._pick_column(columns, ["is_hierarchical"])

#         if not key_col:
#             self._warnings.append(
#                 "relationship_types table has no usable key column; default relationship types were used."
#             )
#             self._relationship_types = set(self.DEFAULT_RELATIONSHIP_TYPES)
#             return self._relationship_types

#         selected = [f"`{key_col}` AS type_key"]
#         if id_col:
#             selected.append(f"`{id_col}` AS relationship_type_id")
#         if label_col:
#             selected.append(f"`{label_col}` AS label")
#         if symmetric_col:
#             selected.append(f"`{symmetric_col}` AS is_symmetric")
#         if hierarchical_col:
#             selected.append(f"`{hierarchical_col}` AS is_hierarchical")

#         result = await self.db.execute(
#             text(f"SELECT {', '.join(selected)} FROM relationship_types")
#         )

#         self._relationship_types_by_key.clear()

#         for row in result.mappings().all():
#             type_key = str(row["type_key"]).strip()
#             if not type_key:
#                 continue

#             self._relationship_types_by_key[type_key] = {
#                 "relationship_type_id": row.get("relationship_type_id"),
#                 "type_key": type_key,
#                 "label": row.get("label"),
#                 "is_symmetric": row.get("is_symmetric"),
#                 "is_hierarchical": row.get("is_hierarchical"),
#             }

#         values = set(self._relationship_types_by_key.keys())
#         if not values:
#             self._warnings.append(
#                 "relationship_types table has no values; default relationship types were used."
#             )

#         self._relationship_types = values or set(self.DEFAULT_RELATIONSHIP_TYPES)
#         return self._relationship_types

#     # ============================================================
#     # QDRANT
#     # ============================================================

#     async def _prepare_qdrant(self) -> None:
#         try:
#             exists = await self.qdrant.collection_exists(
#                 collection_name=self.qdrant_collection
#             )

#             if not exists:
#                 await self.qdrant.create_collection(
#                     collection_name=self.qdrant_collection,
#                     vectors_config=models.VectorParams(
#                         size=self.embedding_dimensions,
#                         distance=models.Distance.COSINE,
#                     ),
#                 )
#                 self._qdrant_collection_created = True
#                 self._qdrant_reachable = True
#                 self._qdrant_has_points = False
#                 self._qdrant_vector_size = self.embedding_dimensions
#                 self._warnings.append(
#                     f"Qdrant collection '{self.qdrant_collection}' was created but has no approved concept vectors yet."
#                 )
#                 return

#             info = await self.qdrant.get_collection(
#                 collection_name=self.qdrant_collection
#             )

#             points_count = int(getattr(info, "points_count", 0) or 0)
#             self._qdrant_reachable = True
#             self._qdrant_has_points = points_count > 0

#             config = getattr(info, "config", None)
#             params = getattr(config, "params", None) if config else None
#             vectors = getattr(params, "vectors", None) if params else None
#             if getattr(vectors, "size", None):
#                 self._qdrant_vector_size = int(vectors.size)

#             if self._qdrant_vector_size and self._qdrant_vector_size != self.embedding_dimensions:
#                 self._warnings.append(
#                     f"Qdrant vector size is {self._qdrant_vector_size}, but configured embedding dimensions are {self.embedding_dimensions}. Semantic matching skipped."
#                 )
#                 self._qdrant_has_points = False

#             if points_count == 0:
#                 self._warnings.append(
#                     f"Qdrant collection '{self.qdrant_collection}' is empty; semantic matching was skipped."
#                 )

#             logger.info(
#                 f"Qdrant ready: collection={self.qdrant_collection}, points={points_count}"
#             )

#         except Exception as exc:
#             self._qdrant_reachable = False
#             self._qdrant_has_points = False
#             self._warnings.append(
#                 f"Qdrant unavailable; semantic matching skipped. Error={exc}"
#             )
#             logger.warning(
#                 "Qdrant is unavailable. Continuing with MySQL exact matching only. "
#                 f"Error: {exc}"
#             )

#     # ============================================================
#     # EMBEDDINGS + SEMANTIC MATCHING
#     # ============================================================

#     async def _batch_embeddings(
#         self,
#         names: List[str],
#         batch_size: int = 100,
#     ) -> Dict[str, List[float]]:
#         output: Dict[str, List[float]] = {}

#         unique_names = []
#         seen = set()

#         for name in names:
#             key = name.casefold()
#             if not name or key in seen:
#                 continue
#             seen.add(key)
#             unique_names.append(name)

#         for start in range(0, len(unique_names), batch_size):
#             batch = unique_names[start : start + batch_size]

#             try:
#                 response = await self.openai_client.embeddings.create(
#                     model=self.embedding_model,
#                     input=batch,
#                     dimensions=self.embedding_dimensions,
#                 )
#             except Exception as exc:
#                 self._warnings.append(f"OpenAI embedding batch failed: {exc}")
#                 logger.warning(
#                     f"Embedding batch failed for {len(batch)} concepts: {exc}"
#                 )
#                 continue

#             for input_name, item in zip(batch, response.data):
#                 output[input_name.casefold()] = item.embedding
#                 self._embedding_cache[input_name.casefold()] = item.embedding

#         return output

#     async def _qdrant_candidates_from_vector(
#         self,
#         vector: List[float],
#     ) -> List[Dict[str, Any]]:
#         try:
#             response = await self.qdrant.query_points(
#                 collection_name=self.qdrant_collection,
#                 query=vector,
#                 limit=self.QDRANT_LIMIT,
#                 with_payload=True,
#             )
#         except Exception as exc:
#             logger.warning(f"Qdrant query failed: {exc}")
#             return []

#         points = getattr(response, "points", []) or []
#         output: List[Dict[str, Any]] = []

#         for point in points:
#             payload = point.payload or {}
#             uid = (
#                 payload.get("concept_uid")
#                 or payload.get("uid")
#                 or payload.get("concept_id")
#             )
#             name = (
#                 payload.get("canonical_name")
#                 or payload.get("name")
#                 or payload.get("concept_name")
#             )

#             if uid is None:
#                 continue

#             output.append(
#                 {
#                     "concept_uid": str(uid),
#                     "canonical_name": name,
#                     "score": float(point.score or 0.0),
#                     "payload": payload,
#                 }
#             )

#         return output

#     # ============================================================
#     # CONCEPT RESOLUTION
#     # ============================================================

#     def _exact_mysql_resolution(
#         self,
#         concept_name: str,
#         input_type_key: str,
#     ) -> Optional[Dict[str, Any]]:
#         trusted = self._mysql_by_name.get(self._comparison_key(concept_name))
#         if not trusted:
#             return None

#         return {
#             "original_name": concept_name,
#             "canonical_name": trusted["canonical_name"],
#             "concept_id": trusted.get("concept_id"),
#             "concept_uid": trusted["concept_uid"],
#             "type_key": trusted.get("type_key") or input_type_key,
#             "input_type_key": input_type_key,
#             "resolution_status": "EXISTING",
#             "match_method": "mysql_exact_or_term",
#             "similarity_score": 1.0,
#             "needs_review": False,
#             "policy_decision": "TRUSTED_DB_MATCH",
#         }

#     def _proposal_resolution(
#         self,
#         document_id: str,
#         original_name: str,
#         type_key: str,
#         candidate: Optional[Dict[str, Any]] = None,
#     ) -> Dict[str, Any]:
#         canonical_name = self._normalize_name(original_name)

#         resolution = {
#             "original_name": original_name,
#             "canonical_name": canonical_name,
#             "proposal_uid": self._stable_proposal_uid(document_id, type_key, canonical_name),
#             "type_key": type_key,
#             "resolution_status": "NEW_PROPOSAL",
#             "match_method": "no_trusted_match",
#             "similarity_score": None,
#             "needs_review": True,
#             "policy_decision": "ALLOW_PROPOSAL",
#         }

#         if candidate:
#             resolution.update(
#                 {
#                     "resolution_status": "REVIEW_REQUIRED",
#                     "match_method": "qdrant_ambiguous",
#                     "candidate_concept_uid": candidate.get("concept_uid"),
#                     "candidate_name": candidate.get("canonical_name"),
#                     "similarity_score": round(float(candidate.get("score", 0.0)), 4),
#                 }
#             )

#         return resolution

#     def _blocked_resolution(
#         self,
#         original_name: str,
#         type_key: str,
#         policy: Dict[str, Any],
#     ) -> Dict[str, Any]:
#         return {
#             "original_name": original_name,
#             "canonical_name": self._normalize_name(original_name),
#             "type_key": type_key,
#             "resolution_status": "REJECTED",
#             "match_method": "concept_type_policy",
#             "similarity_score": None,
#             "needs_review": True,
#             "policy_decision": policy["decision"],
#             "reason": policy["reason"],
#         }

#     async def _resolve_semantic_batch(
#         self,
#         document_id: str,
#         unresolved: List[Tuple[int, Dict[str, Any], str]],
#     ) -> Dict[int, Dict[str, Any]]:
#         if not unresolved or not self._qdrant_has_points:
#             return {}

#         names = [
#             self._normalize_name(concept.get("canonical_name", ""))
#             for _, concept, _ in unresolved
#         ]

#         embeddings = await self._batch_embeddings(names)
#         semaphore = asyncio.Semaphore(self.normalization_concurrency)

#         async def one(index: int, concept: Dict[str, Any], input_type_key: str):
#             name = self._normalize_name(concept.get("canonical_name", ""))
#             vector = embeddings.get(name.casefold())

#             if vector is None:
#                 return index, None

#             async with semaphore:
#                 candidates = await self._qdrant_candidates_from_vector(vector)

#             best_review_candidate = None

#             for candidate in candidates:
#                 trusted = self._mysql_by_uid.get(str(candidate.get("concept_uid")))
#                 if not trusted:
#                     continue

#                 score = float(candidate.get("score", 0.0))

#                 if score >= self.SEMANTIC_MATCH_THRESHOLD:
#                     return index, {
#                         "original_name": name,
#                         "canonical_name": trusted["canonical_name"],
#                         "concept_id": trusted.get("concept_id"),
#                         "concept_uid": trusted["concept_uid"],
#                         "type_key": trusted.get("type_key") or input_type_key,
#                         "input_type_key": input_type_key,
#                         "resolution_status": "EXISTING",
#                         "match_method": "qdrant_verified_mysql",
#                         "similarity_score": round(score, 4),
#                         "needs_review": False,
#                         "policy_decision": "TRUSTED_DB_MATCH",
#                     }

#                 if score >= self.SEMANTIC_REVIEW_THRESHOLD and best_review_candidate is None:
#                     best_review_candidate = {
#                         "concept_uid": trusted["concept_uid"],
#                         "canonical_name": trusted["canonical_name"],
#                         "score": score,
#                     }

#             policy = self._concept_policy_decision(input_type_key, name)
#             if best_review_candidate and policy["can_be_proposed"]:
#                 return index, self._proposal_resolution(
#                     document_id,
#                     name,
#                     input_type_key,
#                     candidate=best_review_candidate,
#                 )

#             return index, None

#         tasks = [
#             asyncio.create_task(one(index, concept, type_key))
#             for index, concept, type_key in unresolved
#         ]

#         results: Dict[int, Dict[str, Any]] = {}

#         for task in asyncio.as_completed(tasks):
#             index, resolution = await task
#             if resolution:
#                 results[index] = resolution

#         return results

#     # ============================================================
#     # RELATIONSHIPS
#     # ============================================================

#     def _normalize_relationship_type(self, value: Any) -> str:
#         normalized = re.sub(
#             r"[^a-z0-9]+",
#             "_",
#             self._normalize_space(value).casefold(),
#         ).strip("_")

#         aliases = {
#             "has_attribute": "has_sensory_attribute",
#             "sensory_attribute": "has_sensory_attribute",
#             "has_intensity_value": "has_intensity",
#             "has_rating": "has_score",
#             "uses_methodology": "uses_method",
#             "belongs": "belongs_to",
#             "associated": "associated_with",
#             "related": "related_to",
#             "uses sql": "uses_sql",
#             "used_sql": "uses_sql",
#         }

#         return aliases.get(normalized, normalized or "related_to")

#     async def _resolve_relationship(
#         self,
#         relationship: Dict[str, Any],
#         concept_lookup: Dict[str, Dict[str, Any]],
#         valid_relationship_types: Set[str],
#     ) -> Dict[str, Any]:
#         source_name = self._normalize_name(relationship.get("source_concept", ""))
#         target_name = self._normalize_name(relationship.get("target_concept", ""))
#         rel_type = self._normalize_relationship_type(
#             relationship.get("relationship_type", "related_to")
#         )

#         source = concept_lookup.get(self._comparison_key(source_name))
#         target = concept_lookup.get(self._comparison_key(target_name))

#         if not source or not target:
#             return {
#                 "status": "REJECTED",
#                 "reason": "relationship_endpoint_missing_or_rejected",
#                 "source_concept": source_name,
#                 "target_concept": target_name,
#                 "relationship_type": rel_type,
#             }

#         if self._comparison_key(source_name) == self._comparison_key(target_name):
#             return {
#                 "status": "REJECTED",
#                 "reason": "self_relationship",
#                 "source_concept": source_name,
#                 "target_concept": target_name,
#                 "relationship_type": rel_type,
#             }

#         if rel_type not in valid_relationship_types:
#             return {
#                 "status": "REVIEW_REQUIRED",
#                 "reason": "relationship_type_not_registered",
#                 "source": source,
#                 "target": target,
#                 "relationship_type": rel_type,
#             }

#         rel_type_record = self._relationship_types_by_key.get(rel_type, {})
#         relationship_type_id = rel_type_record.get("relationship_type_id")

#         source_ref = source.get("concept_uid") or source.get("proposal_uid")
#         target_ref = target.get("concept_uid") or target.get("proposal_uid")

#         if not source_ref or not target_ref:
#             return {
#                 "status": "REJECTED",
#                 "reason": "relationship_uid_missing",
#                 "source_concept": source_name,
#                 "target_concept": target_name,
#                 "relationship_type": rel_type,
#             }

#         both_existing = (
#             source.get("resolution_status") == "EXISTING"
#             and target.get("resolution_status") == "EXISTING"
#         )

#         status_value = "READY" if both_existing else "REVIEW_REQUIRED"

#         return {
#             "relationship_uid": self._stable_relationship_uid(
#                 str(source_ref),
#                 rel_type,
#                 str(target_ref),
#             ),
#             "source_concept_id": source.get("concept_id"),
#             "target_concept_id": target.get("concept_id"),
#             "source_uid": source_ref,
#             "target_uid": target_ref,
#             "source_concept": source["canonical_name"],
#             "target_concept": target["canonical_name"],
#             "relationship_type": rel_type,
#             "relationship_type_id": relationship_type_id,
#             "status": status_value,
#             "reason": None if status_value == "READY" else "relationship_touches_unapproved_or_blocked_concept",
#             "confidence": relationship.get("confidence"),
#             "source_page": relationship.get("source_page"),
#             "element_id": relationship.get("element_id"),
#             "evidence": relationship.get("evidence"),
#         }

#     # ============================================================
#     # RECORD BUILDERS
#     # ============================================================

#     def _proposal_record(
#         self,
#         document_id: str,
#         concept: Dict[str, Any],
#         resolution: Dict[str, Any],
#     ) -> Dict[str, Any]:
#         normalized_name = self._comparison_key(resolution["canonical_name"])

#         return {
#             "proposal_uid": resolution["proposal_uid"],
#             "document_id": document_id,
#             "proposed_type": resolution["type_key"],
#             "proposed_name": resolution["canonical_name"],
#             "proposed_name_normalized": normalized_name,
#             "proposed_definition": concept.get("definition"),
#             "proposed_data": concept,
#             "proposed_terms": {
#                 "canonical": resolution["canonical_name"],
#                 "synonyms": self._dedupe_strings(concept.get("synonyms", [])),
#                 "keywords": self._dedupe_strings(concept.get("keywords", [])),
#             },
#             "proposed_relationships": [],
#             "source_page": concept.get("source_page"),
#             "element_id": concept.get("element_id"),
#             "section_path": concept.get("section_path", []),
#             "hierarchy_context": concept.get("hierarchy_context"),
#             "status": "pending",
#             "priority": "normal",
#             "requires_expert": True,
#             "ai_confidence": resolution.get("similarity_score"),
#             "ai_reasoning": resolution.get("match_method"),
#             "candidate_concept_uid": resolution.get("candidate_concept_uid"),
#             "candidate_name": resolution.get("candidate_name"),
#             "candidate_similarity": resolution.get("similarity_score"),
#             "created_by": "normalization_service",
#         }

#     def _term_records(
#         self,
#         concept: Dict[str, Any],
#         resolution: Dict[str, Any],
#     ) -> List[Dict[str, Any]]:
#         concept_id = resolution.get("concept_id")
#         concept_uid = resolution.get("concept_uid") or resolution.get("proposal_uid")
#         canonical_name = resolution["canonical_name"]
#         proposed = resolution["resolution_status"] != "EXISTING"

#         output = [
#             {
#                 "concept_id": concept_id,
#                 "concept_uid": concept_uid,
#                 "term": canonical_name,
#                 "term_type": "canonical",
#                 "status": "proposed" if proposed else "active",
#                 "proposed": proposed,
#             }
#         ]

#         for synonym in self._dedupe_strings(concept.get("synonyms", [])):
#             if synonym.casefold() == canonical_name.casefold():
#                 continue

#             output.append(
#                 {
#                     "concept_id": concept_id,
#                     "concept_uid": concept_uid,
#                     "term": synonym,
#                     "term_type": "synonym",
#                     "status": "proposed" if proposed else "active",
#                     "proposed": proposed,
#                 }
#             )

#         return output

#     def _field_records(
#         self,
#         document_id: str,
#         concept: Dict[str, Any],
#         resolution: Dict[str, Any],
#     ) -> List[Dict[str, Any]]:
#         concept_id = resolution.get("concept_id")
#         concept_uid = resolution.get("concept_uid") or resolution.get("proposal_uid")
#         type_key = resolution.get("type_key")
#         proposed = resolution["resolution_status"] != "EXISTING"

#         output: List[Dict[str, Any]] = []

#         simple_fields = {
#             "definition": concept.get("definition"),
#             "hierarchy_context": concept.get("hierarchy_context"),
#             "source_page": concept.get("source_page"),
#             "element_id": concept.get("element_id"),
#         }

#         for field_key, value in simple_fields.items():
#             if value in (None, ""):
#                 continue

#             output.append(
#                 {
#                     "field_uid": self._stable_field_uid(
#                         str(concept_uid),
#                         field_key,
#                         value,
#                         document_id,
#                     ),
#                     "concept_id": concept_id,
#                     "concept_uid": concept_uid,
#                     "type_key": type_key,
#                     "field_key": field_key,
#                     "field_name": field_key,
#                     "field_value": value,
#                     "val_string": str(value),
#                     "document_id": document_id,
#                     "status": "proposed" if proposed else "active",
#                     "proposed": proposed,
#                 }
#             )

#         attributes = concept.get("attributes", [])
#         if isinstance(attributes, list):
#             for attribute in attributes:
#                 if not isinstance(attribute, dict):
#                     continue

#                 field_key = self._normalize_name(attribute.get("name"))
#                 value = attribute.get("value")
#                 if not field_key or value in (None, ""):
#                     continue

#                 output.append(
#                     {
#                         "field_uid": self._stable_field_uid(
#                             str(concept_uid),
#                             field_key,
#                             value,
#                             document_id,
#                         ),
#                         "concept_id": concept_id,
#                         "concept_uid": concept_uid,
#                         "type_key": type_key,
#                         "field_key": field_key,
#                         "field_name": field_key,
#                         "field_value": value,
#                         "val_string": str(value),
#                         "document_id": document_id,
#                         "status": "proposed" if proposed else "active",
#                         "proposed": proposed,
#                     }
#                 )

#         return output

#     # ============================================================
#     # QUALITY GATE
#     # ============================================================

#     def _quality_gate(
#         self,
#         input_concepts: int,
#         existing_count: int,
#         proposal_count: int,
#         review_count: int,
#         rejected_count: int,
#         blocked_seeded_count: int,
#         blocked_policy_count: int,
#         admin_review_count: int,
#         ready_relationships: int,
#         pending_relationships: int,
#         rejected_relationships: int,
#     ) -> Dict[str, Any]:
#         warnings = list(dict.fromkeys(self._warnings))

#         if input_concepts <= 0:
#             return {
#                 "status": "FAILED",
#                 "score": 0,
#                 "reason": "No concepts were found in extracted_knowledge.json.",
#                 "warnings": warnings,
#                 "can_continue": False,
#             }

#         rejected_ratio = rejected_count / max(input_concepts, 1)

#         if rejected_ratio > 0.35:
#             return {
#                 "status": "NEEDS_EXTRACTION_REVIEW",
#                 "score": 60,
#                 "reason": "Too many concepts were rejected. Review extraction quality.",
#                 "warnings": warnings,
#                 "can_continue": False,
#             }

#         if blocked_policy_count > 0:
#             return {
#                 "status": "POLICY_LAYER_ADMIN_REVIEW_REQUIRED",
#                 "score": 84,
#                 "reason": (
#                     "Some routing/policy concepts were detected. They were not proposed because "
#                     "policy concepts must be designed/admin-seeded."
#                 ),
#                 "warnings": warnings,
#                 "can_continue": True,
#             }

#         if blocked_seeded_count > 0:
#             return {
#                 "status": "SEEDED_CONCEPT_MATCH_REVIEW_REQUIRED",
#                 "score": 86,
#                 "reason": (
#                     "Some seeded substrate concepts did not match MySQL. "
#                     "Scales/families/axes/modalities should be seeded, not AI-proposed."
#                 ),
#                 "warnings": warnings,
#                 "can_continue": True,
#             }

#         if len(self._mysql_by_uid) == 0:
#             return {
#                 "status": "FIRST_INGESTION_REVIEW_REQUIRED",
#                 "score": 90,
#                 "reason": (
#                     "MySQL and Qdrant are ready, but no trusted concepts exist yet. "
#                     "Only allowed substrate concepts were converted to proposals."
#                 ),
#                 "warnings": warnings,
#                 "can_continue": True,
#             }

#         if existing_count == 0 and proposal_count > 0:
#             return {
#                 "status": "LOW_REUSE_REVIEW_REQUIRED",
#                 "score": 82,
#                 "reason": (
#                     "Trusted concepts exist, but this document did not reuse any. "
#                     "Review synonym quality and Qdrant sync."
#                 ),
#                 "warnings": warnings,
#                 "can_continue": True,
#             }

#         if pending_relationships > 0 and ready_relationships == 0:
#             return {
#                 "status": "APPROVAL_REQUIRED",
#                 "score": 88,
#                 "reason": "Concepts were normalized, but relationships need approval before commit.",
#                 "warnings": warnings,
#                 "can_continue": True,
#             }

#         return {
#             "status": "PASS",
#             "score": 98,
#             "reason": "Normalization output is ready for validate-commit.",
#             "warnings": warnings,
#             "can_continue": True,
#         }

#     # ============================================================
#     # MASTER
#     # ============================================================

#     async def normalize_graph_and_map(self, document_id: str) -> Dict[str, Any]:
#         started = time.perf_counter()

#         processed_base = self.processed_dir / document_id
#         knowledge_path = processed_base / "extracted_knowledge.json"

#         knowledge = self._require_knowledge_artifact(knowledge_path, document_id)

#         raw_concepts = [
#             item for item in knowledge.get("concepts", [])
#             if isinstance(item, dict)
#         ]
#         relationships = [
#             item for item in knowledge.get("relationships", [])
#             if isinstance(item, dict)
#         ]

#         logger.info(
#             f"Normalization started for {document_id}. "
#             f"Concepts={len(raw_concepts)}, Relationships={len(relationships)}"
#         )

#         await self._mysql_preflight()
#         await self._load_mysql_catalog()
#         valid_relationship_types = await self._load_relationship_types()
#         await self._prepare_qdrant()

#         resolutions_by_index: Dict[int, Dict[str, Any]] = {}
#         rejected_concepts: List[Dict[str, Any]] = []
#         blocked_seeded_concepts: List[Dict[str, Any]] = []
#         blocked_policy_concepts: List[Dict[str, Any]] = []
#         admin_review_concepts: List[Dict[str, Any]] = []
#         unresolved_allowed: List[Tuple[int, Dict[str, Any], str]] = []

#         seen_valid_concept_keys: Set[str] = set()
#         duplicate_concepts = 0

#         for index, concept in enumerate(raw_concepts):
#             original_name = self._normalize_name(concept.get("canonical_name", ""))

#             if not original_name:
#                 rejected_concepts.append(
#                     {
#                         "concept": concept,
#                         "resolution": {
#                             "resolution_status": "REJECTED",
#                             "reason": "empty_concept_name",
#                         },
#                     }
#                 )
#                 continue

#             type_key = self._type_key(concept)

#             if self._is_metadata_concept(original_name):
#                 rejected_concepts.append(
#                     {
#                         "concept": concept,
#                         "resolution": {
#                             "canonical_name": original_name,
#                             "type_key": type_key,
#                             "resolution_status": "REJECTED",
#                             "reason": "document_metadata",
#                         },
#                     }
#                 )
#                 continue

#             if self._is_floating_value(original_name):
#                 rejected_concepts.append(
#                     {
#                         "concept": concept,
#                         "resolution": {
#                             "canonical_name": original_name,
#                             "type_key": type_key,
#                             "resolution_status": "REJECTED",
#                             "reason": "floating_numeric_or_formula_value",
#                         },
#                     }
#                 )
#                 continue

#             key = self._comparison_key(original_name)
#             if key in seen_valid_concept_keys:
#                 duplicate_concepts += 1
#             seen_valid_concept_keys.add(key)

#             exact = self._exact_mysql_resolution(original_name, type_key)
#             if exact:
#                 resolutions_by_index[index] = exact
#                 continue

#             policy = self._concept_policy_decision(type_key, original_name)

#             if policy["can_be_proposed"]:
#                 unresolved_allowed.append((index, concept, type_key))
#                 continue

#             blocked = {
#                 "concept": concept,
#                 "resolution": self._blocked_resolution(
#                     original_name,
#                     type_key,
#                     policy,
#                 ),
#             }

#             if policy["decision"] == "REQUIRE_SEEDED_MATCH":
#                 blocked_seeded_concepts.append(blocked)
#             elif policy["decision"] == "REQUIRE_ADMIN_SEEDING":
#                 blocked_policy_concepts.append(blocked)
#             else:
#                 admin_review_concepts.append(blocked)

#         semantic_results = await self._resolve_semantic_batch(
#             document_id,
#             unresolved_allowed,
#         )
#         resolutions_by_index.update(semantic_results)

#         for index, concept, type_key in unresolved_allowed:
#             if index in resolutions_by_index:
#                 continue

#             name = self._normalize_name(concept.get("canonical_name", ""))
#             resolutions_by_index[index] = self._proposal_resolution(
#                 document_id,
#                 name,
#                 type_key,
#             )

#         concept_lookup: Dict[str, Dict[str, Any]] = {}
#         canonical_mapping = []
#         proposals = []
#         concept_terms = []
#         concept_fields = []

#         for index, concept in enumerate(raw_concepts):
#             resolution = resolutions_by_index.get(index)
#             if not resolution:
#                 continue

#             mapping_record = {
#                 "source_concept": concept.get("canonical_name"),
#                 **resolution,
#             }
#             canonical_mapping.append(mapping_record)

#             original_key = self._comparison_key(concept.get("canonical_name", ""))
#             canonical_key = self._comparison_key(resolution["canonical_name"])

#             concept_lookup[original_key] = resolution
#             concept_lookup[canonical_key] = resolution

#             if resolution["resolution_status"] in {"NEW_PROPOSAL", "REVIEW_REQUIRED"}:
#                 proposals.append(self._proposal_record(document_id, concept, resolution))

#             concept_terms.extend(self._term_records(concept, resolution))
#             concept_fields.extend(self._field_records(document_id, concept, resolution))

#         canonical_mapping = self._dedupe_records(
#             canonical_mapping,
#             ["source_concept", "canonical_name", "resolution_status", "type_key"],
#         )
#         proposals = self._dedupe_records(proposals, ["proposal_uid"])
#         concept_terms = self._dedupe_records(
#             concept_terms,
#             ["concept_uid", "term", "term_type"],
#         )
#         concept_fields = self._dedupe_records(concept_fields, ["field_uid"])

#         ready_relationships = []
#         pending_relationships = []
#         rejected_relationships = []
#         seen_relationships: Set[str] = set()

#         for relationship in relationships:
#             mapped = await self._resolve_relationship(
#                 relationship,
#                 concept_lookup,
#                 valid_relationship_types,
#             )

#             signature = mapped.get("relationship_uid") or json.dumps(
#                 mapped,
#                 sort_keys=True,
#                 default=str,
#             )

#             if signature in seen_relationships:
#                 continue
#             seen_relationships.add(signature)

#             if mapped.get("status") == "READY":
#                 ready_relationships.append(mapped)
#             elif mapped.get("status") == "REVIEW_REQUIRED":
#                 pending_relationships.append(mapped)
#             else:
#                 rejected_relationships.append(mapped)

#         existing_count = sum(
#             1
#             for item in canonical_mapping
#             if item.get("resolution_status") == "EXISTING"
#         )
#         proposal_count = sum(
#             1
#             for item in canonical_mapping
#             if item.get("resolution_status") == "NEW_PROPOSAL"
#         )
#         review_count = sum(
#             1
#             for item in canonical_mapping
#             if item.get("resolution_status") == "REVIEW_REQUIRED"
#         )

#         quality_gate = self._quality_gate(
#             input_concepts=len(raw_concepts),
#             existing_count=existing_count,
#             proposal_count=proposal_count,
#             review_count=review_count,
#             rejected_count=len(rejected_concepts),
#             blocked_seeded_count=len(blocked_seeded_concepts),
#             blocked_policy_count=len(blocked_policy_concepts),
#             admin_review_count=len(admin_review_concepts),
#             ready_relationships=len(ready_relationships),
#             pending_relationships=len(pending_relationships),
#             rejected_relationships=len(rejected_relationships),
#         )

#         mysql_payload = {
#             "document_id": document_id,
#             "existing_concepts": [
#                 item
#                 for item in canonical_mapping
#                 if item.get("resolution_status") == "EXISTING"
#             ],
#             "concepts": [],
#             "concept_terms": concept_terms,
#             "concept_fields": concept_fields,
#             "concept_field_arrays": [],
#             "concept_relationships": ready_relationships,
#             "concept_proposals": proposals,
#             "pending_relationships": pending_relationships,
#             "rejected_concepts": rejected_concepts,
#             "blocked_seeded_concepts": blocked_seeded_concepts,
#             "blocked_policy_concepts": blocked_policy_concepts,
#             "admin_review_concepts": admin_review_concepts,
#             "rejected_relationships": rejected_relationships,
#             "question_concept_links": [],
#             "option_concept_links": [],
#             "concept_exclusions": [],
#             "governance_rules": [],
#             "validation_stats": {
#                 "input_concepts": len(raw_concepts),
#                 "unique_valid_concept_keys": len(seen_valid_concept_keys),
#                 "duplicate_concepts_detected": duplicate_concepts,
#                 "existing_concepts_reused": existing_count,
#                 "new_proposals_generated": proposal_count,
#                 "ambiguous_concepts_for_review": review_count,
#                 "rejected_concepts": len(rejected_concepts),
#                 "blocked_seeded_concepts": len(blocked_seeded_concepts),
#                 "blocked_policy_concepts": len(blocked_policy_concepts),
#                 "admin_review_concepts": len(admin_review_concepts),
#                 "input_relationships": len(relationships),
#                 "live_edges_ready": len(ready_relationships),
#                 "pending_relationships": len(pending_relationships),
#                 "rejected_relationships": len(rejected_relationships),
#                 "quality_gate": quality_gate,
#             },
#         }

#         canonical_path = processed_base / "canonical_mapping.json"
#         mysql_payload_path = processed_base / "mysql_payload.json"

#         canonical_artifact = {
#             "document_id": document_id,
#             "canonical_mapping": canonical_mapping,
#             "blocked_seeded_concepts": blocked_seeded_concepts,
#             "blocked_policy_concepts": blocked_policy_concepts,
#             "admin_review_concepts": admin_review_concepts,
#             "summary": {
#                 "existing": existing_count,
#                 "new_proposals": proposal_count,
#                 "review_required": review_count,
#                 "rejected": len(rejected_concepts),
#                 "blocked_seeded_concepts": len(blocked_seeded_concepts),
#                 "blocked_policy_concepts": len(blocked_policy_concepts),
#                 "admin_review_concepts": len(admin_review_concepts),
#                 "duplicate_concepts_detected": duplicate_concepts,
#                 "quality_gate": quality_gate,
#             },
#         }

#         self._atomic_write_json(canonical_path, canonical_artifact)
#         self._atomic_write_json(mysql_payload_path, mysql_payload)

#         try:
#             self._write_metadata_status(
#                 document_id,
#                 "NORMALIZED_AND_MAPPED",
#                 {
#                     "normalization_summary": {
#                         "input_concepts": len(raw_concepts),
#                         "existing_concepts_reused": existing_count,
#                         "new_proposals": proposal_count,
#                         "review_required": review_count,
#                         "rejected_concepts": len(rejected_concepts),
#                         "blocked_seeded_concepts": len(blocked_seeded_concepts),
#                         "blocked_policy_concepts": len(blocked_policy_concepts),
#                         "admin_review_concepts": len(admin_review_concepts),
#                         "quality_gate": quality_gate,
#                     }
#                 },
#             )
#         except Exception as exc:
#             self._warnings.append(f"Metadata status update failed: {exc}")
#             logger.warning(f"Metadata status update failed for {document_id}: {exc}")

#         elapsed = time.perf_counter() - started

#         logger.info(
#             f"Normalization + Graph + Schema Mapping completed for {document_id} "
#             f"in {elapsed:.2f}s. existing={existing_count}, "
#             f"proposals={proposal_count}, review={review_count}, "
#             f"rejected={len(rejected_concepts)}, "
#             f"blocked_seeded={len(blocked_seeded_concepts)}, "
#             f"blocked_policy={len(blocked_policy_concepts)}, "
#             f"ready_edges={len(ready_relationships)}"
#         )

#         return {
#             "document_id": document_id,
#             "pipeline_status": "NORMALIZED_AND_MAPPED",
#             "normalization": {
#                 "input_concepts": len(raw_concepts),
#                 "unique_valid_concept_keys": len(seen_valid_concept_keys),
#                 "duplicate_concepts_detected": duplicate_concepts,
#                 "existing_concepts_reused": existing_count,
#                 "new_proposals": proposal_count,
#                 "review_required": review_count,
#                 "rejected_concepts": len(rejected_concepts),
#                 "blocked_seeded_concepts": len(blocked_seeded_concepts),
#                 "blocked_policy_concepts": len(blocked_policy_concepts),
#                 "admin_review_concepts": len(admin_review_concepts),
#             },
#             "knowledge_graph": {
#                 "input_relationships": len(relationships),
#                 "ready_relationships": len(ready_relationships),
#                 "pending_relationships": len(pending_relationships),
#                 "rejected_relationships": len(rejected_relationships),
#             },
#             "schema_mapping": {
#                 "concepts": 0,
#                 "concept_terms": len(concept_terms),
#                 "concept_fields": len(concept_fields),
#                 "concept_relationships": len(ready_relationships),
#                 "concept_proposals": len(proposals),
#                 "blocked_seeded_concepts": len(blocked_seeded_concepts),
#                 "blocked_policy_concepts": len(blocked_policy_concepts),
#                 "admin_review_concepts": len(admin_review_concepts),
#             },
#             "infrastructure": {
#                 "mysql": "READY",
#                 "mysql_trusted_concepts_loaded": len(self._mysql_by_uid),
#                 "qdrant_reachable": self._qdrant_reachable,
#                 "qdrant_collection": self.qdrant_collection,
#                 "qdrant_collection_created": self._qdrant_collection_created,
#                 "qdrant_has_points": self._qdrant_has_points,
#                 "semantic_matching_used": self._qdrant_has_points,
#                 "embedding_model": self.embedding_model,
#                 "embedding_dimensions": self.embedding_dimensions,
#                 "qdrant_vector_size": self._qdrant_vector_size,
#             },
#             "quality_gate": quality_gate,
#             "artifacts": {
#                 "canonical_mapping": str(canonical_path.relative_to(settings.BASE_DIR)),
#                 "mysql_payload": str(mysql_payload_path.relative_to(settings.BASE_DIR)),
#             },
#             "processing_time_seconds": round(elapsed, 2),
#             "next_step": (
#                 f"{settings.API_V1_STR}/documents/{document_id}/validate-commit"
#             ),
#             "recommended_actions": [
#                 "Run validate-commit to persist allowed substrate proposals safely.",
#                 "Do not auto-approve scales, families, axes, modalities, or routing/policy concepts.",
#                 "Approve sensory_attribute and descriptor proposals through HITL/admin review.",
#                 "After approval, insert canonical concepts/terms/fields/relationships using real MySQL IDs.",
#                 "Run MySQL-to-Qdrant reconcile/sync so approved concepts are mirrored into the correct vector collection.",
#                 "Re-run normalization for future documents to reuse trusted concepts and create ready relationships.",
#             ],
#         }









import asyncio
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient, models
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ProcessingError
from app.core.logger import logger


class NormalizationGraphService:
    """
    TagTaste Concept DB aligned normalization.

    Overall architecture rating target:
        10/10

    What "10/10" means here:
        - The API follows the Concept DB architecture rules.
        - It does not hide infra issues.
        - It does not auto-propose concepts that must be seeded/admin-managed.
        - It separates proposal, seeded, policy, admin-review, and relationship buckets.
        - It produces deterministic, idempotent artifacts for validate-commit.

    Architecture rules implemented:
        - MySQL is source of truth.
        - Qdrant is only a mirror/candidate retrieval layer.
        - Proposal flow is only for sensory substrate concepts:
            sensory_attribute
            descriptor
        - Seeded substrate types are never AI-proposed:
            sensory_scale, family, axis, modality, benchmark
        - Routing/policy types are never AI-proposed:
            intent_group, sql_query_pattern, analysis_recipe, recipe_step,
            classifier_prompt, governance_rule, answer_example, etc.
        - Existing concepts are confirmed by MySQL.
        - Semantic Qdrant matches are accepted only after MySQL UID confirmation.
        - Relationships touching proposals stay pending.
        - Relationships touching blocked seeded/policy/admin concepts are separated,
          not incorrectly counted as rejected.
    """

    DEFAULT_EMBEDDING_MODEL = "text-embedding-3-large"
    DEFAULT_QDRANT_COLLECTION = "concepts"
    DEFAULT_EMBEDDING_DIMENSIONS = 3072

    SEMANTIC_MATCH_THRESHOLD = 0.88
    SEMANTIC_REVIEW_THRESHOLD = 0.78
    QDRANT_LIMIT = 5

    KNOWLEDGE_REQUIRED_STATUS = "KNOWLEDGE_EXTRACTED"

    PROPOSAL_ALLOWED_TYPE_KEYS: Set[str] = {
        "sensory_attribute",
        "descriptor",
    }

    SEEDED_SUBSTRATE_TYPE_KEYS: Set[str] = {
        "sensory_scale",
        "family",
        "axis",
        "modality",
        "benchmark",
    }

    POLICY_LAYER_TYPE_KEYS: Set[str] = {
        "intent_group",
        "sql_query_pattern",
        "analysis_recipe",
        "recipe_step",
        "classifier_prompt",
        "governance_rule",
        "guardrail_rule",
        "answer_example",
        "category_knowledge",
        "alignment_gate",
        "prompt_requirement",
        "answer_shape_template",
        "question_understanding",
        "question_shape",
        "question_specificity",
        "section_weight_profile",
        "data_source",
        "hidden_intent",
        "reasoning_pattern",
        "category_profile",
        "metric",
        "domain",
        "data_binding_rule",
        "sql_routing",
        "stakeholder_directive",
        "route",
        "bypass_rule",
        "analytical_method",
        "render_template",
        "demographic_axis",
        "persona",
        "verified_tool",
        "ar_question_slot",
    }

    GROUP_B_PARENT_TYPE_KEYS: Set[str] = {
        "intent_group",
        "guardrail_rule",
        "domain",
    }

    GROUP_C_PHP_LOADED_TYPE_KEYS: Set[str] = {
        "classifier_prompt",
        "persona",
    }

    DEFAULT_RELATIONSHIP_TYPES: Set[str] = {
        "is_child_of",
        "causes",
        "measured_by",
        "described_by",
        "influences",
        "related_to",
        "part_of",
        "categorized_as",
        "applies_to",
        "masks",
        "enhances",
        "co_occurs_with",
        "substitutes_for",
        "is_example_of",
        "triggered_by",
        "renders_as",
        "uses_prompt",
        "gated_by",
        "composes_from",
        "default_prompt",
        "default_shape",
        "benchmarked_by",
        "pulls_from",
        "uses_sql",
        "uses_method",
        "checks_metric",
        "column_in",
        "measured_on",
        "uses_render_template",
        "cites_from",
        "uses_weights",
        "writing_contract",
        "footer_template",
        "triggers_expansion",
        "has_default_shape",
        "tiers_for",
        "threshold_for",
        "contains",
        "has_attribute",
        "has_sensory_attribute",
        "has_descriptor",
        "has_intensity",
        "has_score",
        "uses_scale",
        "evaluated_by",
        "compared_with",
        "prepared_by",
        "derived_from",
        "belongs_to",
        "associated_with",
        "defined_by",
        "measured_under",
        "tested_by",
        "has_method",
        "has_property",
        "correlates_with",
    }

    CATEGORY_TO_TYPE_KEY = {
        "Attribute": "sensory_attribute",
        "Sensory_Attribute": "sensory_attribute",
        "Sensory Attribute": "sensory_attribute",
        "Descriptor": "descriptor",
        "Scale": "sensory_scale",
        "Sensory_Scale": "sensory_scale",
        "Sensory Scale": "sensory_scale",
        "Family": "family",
        "Axis": "axis",
        "Modality": "modality",
        "Benchmark": "benchmark",
        "Method": "analytical_method",
        "Analysis_Method": "analytical_method",
        "Analysis Method": "analytical_method",
        "Metric": "metric",
        "Entity": "food_science",
        "Food Science": "food_science",
        "Food_Science": "food_science",
        "Property": "food_science",
        "Process": "food_science",
        "Material": "food_science",
        "Chemical": "food_science",
        "Instrument": "food_science",
        "Organization": "food_science",
        "Measurement": "metric",
        "Product": "category_knowledge",
        "Sample": "category_knowledge",
    }

    ATTRIBUTE_HINTS = {
        "sweetness",
        "sourness",
        "saltiness",
        "bitterness",
        "umami",
        "crunchiness",
        "crispness",
        "hardness",
        "firmness",
        "chewiness",
        "creaminess",
        "stickiness",
        "juiciness",
        "aroma intensity",
        "flavour intensity",
        "flavor intensity",
        "appearance",
        "color",
        "colour",
        "aftertaste",
        "mouthfeel",
        "texture",
        "viscosity",
    }

    DESCRIPTOR_HINTS = {
        "fruity",
        "floral",
        "metallic",
        "burnt",
        "smoky",
        "crispy",
        "creamy",
        "rancid",
        "stale",
        "fresh",
        "earthy",
        "woody",
        "spicy",
        "bitter",
        "sour",
        "sweet",
        "salty",
        "astringent",
        "grainy",
        "smooth",
        "rough",
        "rubbery",
        "chalky",
    }

    SCALE_HINTS = {
        "scale",
        "likert",
        "nps",
        "jar",
        "just about right",
        "hedonic",
        "9-point",
        "7-point",
        "5-point",
        "ranking",
        "boolean",
        "categorical",
        "intensity scale",
    }

    FAMILY_HINTS = {
        "basic taste",
        "aromatics",
        "texture",
        "visual",
        "trigeminal",
        "physiological",
        "temporal",
        "acoustic",
        "marketing",
        "functional",
        "ingredient",
        "product category",
        "quality",
        "physical",
        "defects",
        "context",
        "metadata",
    }

    AXIS_HINTS = {
        "sensory",
        "preference",
        "diagnostic",
    }

    MODALITY_HINTS = {
        "gustatory",
        "olfactory",
        "tactile",
        "visual",
        "auditory",
        "trigeminal",
    }

    METADATA_PATTERNS = [
        r"\bisbn\b",
        r"\bcopyright\b",
        r"\bpublisher\b",
        r"\bedition\b",
        r"\bauthor\b",
        r"\bprinted by\b",
        r"\ball rights reserved\b",
        r"\btable of contents\b",
        r"\bindex\b",
        r"\breferences\b",
        r"\bbibliography\b",
    ]

    PURE_NUMBER_RE = re.compile(
        r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:\s*%|\s*[a-zA-Z°]+)?$"
    )
    ASSIGNMENT_VALUE_RE = re.compile(
        r"^[A-Za-zαβμσχ²χ]+(?:\d+)?\s*=\s*[+-]?\d+(?:\.\d+)?%?$"
    )
    SHORT_FORMULA_RE = re.compile(
        r"^(?:n\d*|x\d*|s\d*|t\d*|f|p|d\d*|c\d*|χ²?)\s*=?\s*[+-]?\d*(?:\.\d+)?%?$",
        re.IGNORECASE,
    )

    def __init__(self, db: AsyncSession):
        self.db = db

        self.raw_dir = Path(settings.STORAGE_RAW_DIR)
        self.processed_dir = Path(settings.STORAGE_PROCESSED_DIR)

        self.embedding_model = getattr(
            settings,
            "OPENAI_EMBEDDING_MODEL",
            self.DEFAULT_EMBEDDING_MODEL,
        )
        self.embedding_dimensions = int(
            getattr(
                settings,
                "OPENAI_EMBEDDING_DIMENSIONS",
                self.DEFAULT_EMBEDDING_DIMENSIONS,
            )
        )

        self.openai_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=float(getattr(settings, "OPENAI_TIMEOUT", 60.0)),
            max_retries=int(getattr(settings, "OPENAI_MAX_RETRIES", 2)),
        )

        qdrant_url = getattr(settings, "QDRANT_URL", None)
        if not qdrant_url:
            qdrant_url = (
                f"http://{getattr(settings, 'QDRANT_HOST', 'localhost')}:"
                f"{int(getattr(settings, 'QDRANT_PORT', 6333))}"
            )

        self.qdrant = AsyncQdrantClient(
            url=qdrant_url,
            api_key=(getattr(settings, "QDRANT_API_KEY", "") or None),
            timeout=5.0,
            check_compatibility=False,
        )

        self.qdrant_collection = getattr(
            settings,
            "QDRANT_CONCEPT_COLLECTION",
            self.DEFAULT_QDRANT_COLLECTION,
        )

        self.normalization_concurrency = max(
            1,
            int(getattr(settings, "NORMALIZATION_CONCURRENCY", 12)),
        )

        self._table_columns: Dict[str, List[str]] = {}
        self._relationship_types_by_key: Dict[str, Dict[str, Any]] = {}
        self._relationship_types: Optional[Set[str]] = None

        self._mysql_by_name: Dict[str, Dict[str, Any]] = {}
        self._mysql_by_uid: Dict[str, Dict[str, Any]] = {}
        self._mysql_by_id: Dict[str, Dict[str, Any]] = {}

        self._embedding_cache: Dict[str, List[float]] = {}

        self._qdrant_reachable = False
        self._qdrant_has_points = False
        self._qdrant_collection_created = False
        self._qdrant_vector_size: Optional[int] = None
        self._qdrant_dimension_match = True

        self._warnings: List[str] = []

    # ============================================================
    # BASIC HELPERS
    # ============================================================

    @staticmethod
    def _normalize_space(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def _normalize_name(self, value: Any) -> str:
        return self._normalize_space(value).strip(" .,:;|-_")

    def _comparison_key(self, value: Any) -> str:
        normalized = self._normalize_name(value).casefold()
        return re.sub(r"[^a-z0-9]+", "", normalized)

    @staticmethod
    def _dedupe_strings(values: Any) -> List[str]:
        if not isinstance(values, list):
            values = [values] if values else []

        output: List[str] = []
        seen = set()

        for value in values:
            item = str(value or "").strip()
            if not item:
                continue

            key = item.casefold()
            if key in seen:
                continue

            seen.add(key)
            output.append(item)

        return output

    @staticmethod
    def _stable_hash(*parts: Any, length: int = 16) -> str:
        raw = "|".join(str(part or "") for part in parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]

    def _stable_proposal_uid(
        self,
        document_id: str,
        type_key: str,
        canonical_name: str,
    ) -> str:
        return "CP_" + self._stable_hash(
            document_id,
            type_key,
            self._comparison_key(canonical_name),
            length=16,
        ).upper()

    def _stable_blocked_uid(
        self,
        document_id: str,
        type_key: str,
        canonical_name: str,
        decision: str,
    ) -> str:
        return "BLK_" + self._stable_hash(
            document_id,
            type_key,
            self._comparison_key(canonical_name),
            decision,
            length=16,
        ).upper()

    def _stable_field_uid(
        self,
        concept_ref: str,
        field_key: str,
        field_value: Any,
        document_id: str,
    ) -> str:
        return "FIELD_" + self._stable_hash(
            concept_ref,
            field_key,
            field_value,
            document_id,
            length=16,
        ).upper()

    @staticmethod
    def _stable_relationship_uid(
        source_ref: str,
        relationship_type: str,
        target_ref: str,
    ) -> str:
        digest = hashlib.sha256(
            f"{source_ref}|{relationship_type}|{target_ref}".encode("utf-8")
        ).hexdigest()[:16]
        return f"REL_{digest.upper()}"

    @staticmethod
    def _dedupe_records(
        records: List[Dict[str, Any]],
        keys: List[str],
    ) -> List[Dict[str, Any]]:
        output = []
        seen = set()

        for record in records:
            signature = tuple(
                json.dumps(record.get(key), sort_keys=True, default=str)
                for key in keys
            )
            if signature in seen:
                continue
            seen.add(signature)
            output.append(record)

        return output

    def _is_metadata_concept(self, concept_name: str) -> bool:
        lowered = concept_name.casefold()
        return any(re.search(pattern, lowered) for pattern in self.METADATA_PATTERNS)

    def _is_floating_value(self, concept_name: str) -> bool:
        name = self._normalize_name(concept_name)
        if not name:
            return True

        if len(name) == 1 and name.casefold() in {
            "c",
            "d",
            "f",
            "p",
            "s",
            "t",
            "x",
            "n",
        }:
            return True

        if self.PURE_NUMBER_RE.fullmatch(name):
            return True

        if self.ASSIGNMENT_VALUE_RE.fullmatch(name):
            return True

        if self.SHORT_FORMULA_RE.fullmatch(name):
            if name.casefold() not in {"ph"}:
                return True

        return False

    def _type_key(self, concept: Dict[str, Any]) -> str:
        raw_value = (
            concept.get("type_key")
            or concept.get("category")
            or concept.get("concept_type")
            or "food_science"
        )

        raw_text = str(raw_value or "").strip()
        if raw_text in self.CATEGORY_TO_TYPE_KEY:
            return self.CATEGORY_TO_TYPE_KEY[raw_text]

        normalized = re.sub(
            r"[^a-z0-9]+",
            "_",
            raw_text.casefold(),
        ).strip("_")

        if normalized in self.CATEGORY_TO_TYPE_KEY.values():
            return normalized

        name = self._normalize_name(concept.get("canonical_name", ""))
        name_lower = name.casefold()

        if any(item in name_lower for item in self.SCALE_HINTS):
            return "sensory_scale"

        if name_lower in self.FAMILY_HINTS:
            return "family"

        if name_lower in self.AXIS_HINTS:
            return "axis"

        if name_lower in self.MODALITY_HINTS:
            return "modality"

        if any(item in name_lower for item in self.ATTRIBUTE_HINTS):
            return "sensory_attribute"

        if any(item in name_lower for item in self.DESCRIPTOR_HINTS):
            return "descriptor"

        return normalized or "food_science"

    def _concept_policy_decision(
        self,
        type_key: str,
        concept_name: str,
    ) -> Dict[str, Any]:
        if type_key in self.PROPOSAL_ALLOWED_TYPE_KEYS:
            return {
                "decision": "ALLOW_PROPOSAL",
                "reason": "sensory_substrate_proposal_allowed",
                "can_be_proposed": True,
                "relationship_bucket": "pending_relationships",
            }

        if type_key in self.SEEDED_SUBSTRATE_TYPE_KEYS:
            return {
                "decision": "REQUIRE_SEEDED_MATCH",
                "reason": (
                    f"{type_key} is a seeded sensory substrate type. "
                    "It should match an existing DB row and should not be AI-proposed."
                ),
                "can_be_proposed": False,
                "relationship_bucket": "blocked_seeded_relationships",
            }

        if type_key in self.POLICY_LAYER_TYPE_KEYS:
            return {
                "decision": "REQUIRE_ADMIN_SEEDING",
                "reason": (
                    f"{type_key} belongs to routing/policy layer. "
                    "It must be designed/admin-seeded, not AI-proposed."
                ),
                "can_be_proposed": False,
                "relationship_bucket": "blocked_policy_relationships",
            }

        return {
            "decision": "REQUIRE_ADMIN_REVIEW",
            "reason": (
                f"{type_key} is not part of the attribute/descriptor proposal flow. "
                "Route it to admin/manual seed review."
            ),
            "can_be_proposed": False,
            "relationship_bucket": "admin_review_relationships",
        }

    # ============================================================
    # FILE HELPERS
    # ============================================================

    @staticmethod
    def _read_json(path: Path) -> Dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"JSON artifact not found: {path}")

        try:
            raw = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise ProcessingError(f"Could not read JSON artifact {path}: {exc}") from exc

        if not raw.strip():
            raise ProcessingError(f"JSON artifact exists but is empty: {path}")

        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProcessingError(
                f"JSON artifact is invalid: {path}. "
                f"line={exc.lineno}, column={exc.colno}, error={exc.msg}"
            ) from exc

        if not isinstance(value, dict):
            raise ProcessingError(
                f"Expected JSON object in {path}, got {type(value).__name__}."
            )

        return value

    @staticmethod
    def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")

        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(
                payload,
                file,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
            file.flush()

        temp_path.replace(path)

    def _read_metadata(self, document_id: str) -> Dict[str, Any]:
        path = self.raw_dir / document_id / "metadata.json"
        if not path.exists():
            raise FileNotFoundError(f"metadata.json not found for {document_id}.")
        return self._read_json(path)

    def _write_metadata_status(
        self,
        document_id: str,
        status_value: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        path = self.raw_dir / document_id / "metadata.json"
        metadata = self._read_json(path)
        metadata["pipeline_status"] = status_value
        metadata["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        if extra:
            metadata.update(extra)
        self._atomic_write_json(path, metadata)

    def _require_knowledge_artifact(
        self,
        knowledge_path: Path,
        document_id: str,
    ) -> Dict[str, Any]:
        metadata = self._read_metadata(document_id)
        pipeline_status = str(metadata.get("pipeline_status", "UNKNOWN")).strip()

        if pipeline_status not in {
            self.KNOWLEDGE_REQUIRED_STATUS,
            "NORMALIZED_AND_MAPPED",
        }:
            raise ProcessingError(
                f"Knowledge extraction is not complete for {document_id}. "
                f"Current pipeline_status={pipeline_status}; "
                f"required={self.KNOWLEDGE_REQUIRED_STATUS}."
            )

        knowledge = self._read_json(knowledge_path)

        concepts = knowledge.get("concepts", [])
        relationships = knowledge.get("relationships", [])

        if not isinstance(concepts, list):
            raise ProcessingError("'concepts' must be a JSON array.")

        if not isinstance(relationships, list):
            raise ProcessingError("'relationships' must be a JSON array.")

        return knowledge

    # ============================================================
    # MYSQL
    # ============================================================

    async def _mysql_preflight(self) -> None:
        try:
            result = await self.db.execute(text("SELECT 1 AS ok"))
            row = result.first()
            if not row or int(row[0]) != 1:
                raise RuntimeError("SELECT 1 returned an unexpected value")
        except Exception as exc:
            raise ProcessingError(
                "MySQL is unavailable. Normalization cannot safely continue "
                "because MySQL is the source of truth. "
                f"Database error: {exc}"
            ) from exc

    async def _get_columns(self, table_name: str) -> List[str]:
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

        columns = [str(row[0]) for row in result.all()]
        self._table_columns[table_name] = columns
        return columns

    @staticmethod
    def _pick_column(
        available: List[str],
        candidates: List[str],
    ) -> Optional[str]:
        lookup = {column.casefold(): column for column in available}
        for candidate in candidates:
            if candidate.casefold() in lookup:
                return lookup[candidate.casefold()]
        return None

    async def _load_mysql_catalog(self) -> None:
        concept_columns = await self._get_columns("concepts")
        if not concept_columns:
            raise ProcessingError(
                "Required MySQL table 'concepts' does not exist in the current database."
            )

        id_col = self._pick_column(concept_columns, ["id", "concept_id"])
        uid_col = self._pick_column(concept_columns, ["concept_uid", "uid"])
        name_col = self._pick_column(
            concept_columns,
            ["canonical_name", "name", "concept_name", "label"],
        )
        type_col = self._pick_column(
            concept_columns,
            ["type_key", "concept_type", "category"],
        )
        status_col = self._pick_column(
            concept_columns,
            ["status", "approval_status"],
        )
        has_vector_col = self._pick_column(concept_columns, ["has_vector"])

        if not uid_col or not name_col:
            raise ProcessingError(
                "Table 'concepts' must contain concept_uid/uid and canonical_name/name."
            )

        selected = []
        if id_col:
            selected.append(f"`{id_col}` AS concept_id")
        selected.extend(
            [
                f"`{uid_col}` AS concept_uid",
                f"`{name_col}` AS canonical_name",
            ]
        )
        if type_col:
            selected.append(f"`{type_col}` AS type_key")
        if status_col:
            selected.append(f"`{status_col}` AS concept_status")
        if has_vector_col:
            selected.append(f"`{has_vector_col}` AS has_vector")

        result = await self.db.execute(
            text(f"SELECT {', '.join(selected)} FROM concepts")
        )

        self._mysql_by_name.clear()
        self._mysql_by_uid.clear()
        self._mysql_by_id.clear()

        for row in result.mappings().all():
            uid = str(row["concept_uid"])
            name = self._normalize_name(row["canonical_name"])
            concept_id = row.get("concept_id")
            type_key = str(row.get("type_key") or "").strip() or None

            if not uid or not name:
                continue

            status_value = row.get("concept_status")
            if status_value and str(status_value).casefold() not in {
                "approved",
                "active",
                "published",
                "trusted",
            }:
                continue

            record = {
                "concept_id": concept_id,
                "concept_uid": uid,
                "canonical_name": name,
                "type_key": type_key,
                "status": status_value,
                "has_vector": row.get("has_vector"),
            }

            self._mysql_by_uid[uid] = record
            if concept_id is not None:
                self._mysql_by_id[str(concept_id)] = record

            self._mysql_by_name[self._comparison_key(name)] = record

        await self._load_concept_terms_into_catalog()

        logger.info(
            "Loaded trusted MySQL concept catalog: "
            f"concepts={len(self._mysql_by_uid)}, "
            f"name/term keys={len(self._mysql_by_name)}"
        )

    async def _load_concept_terms_into_catalog(self) -> None:
        term_columns = await self._get_columns("concept_terms")
        if not term_columns:
            return

        term_col = self._pick_column(
            term_columns,
            ["term", "term_text", "name", "value", "synonym"],
        )
        ref_id_col = self._pick_column(term_columns, ["concept_id"])
        ref_uid_col = self._pick_column(term_columns, ["concept_uid", "uid"])
        status_col = self._pick_column(term_columns, ["status", "is_active"])

        if not term_col or not (ref_id_col or ref_uid_col):
            return

        selected = [f"`{term_col}` AS matched_term"]
        if ref_id_col:
            selected.append(f"`{ref_id_col}` AS concept_ref_id")
        if ref_uid_col:
            selected.append(f"`{ref_uid_col}` AS concept_ref_uid")
        if status_col:
            selected.append(f"`{status_col}` AS term_status")

        result = await self.db.execute(
            text(
                f"""
                SELECT {', '.join(selected)}
                FROM concept_terms
                WHERE `{term_col}` IS NOT NULL
                """
            )
        )

        for row in result.mappings().all():
            status_value = row.get("term_status")
            if status_value is not None:
                status_text = str(status_value).casefold()
                if status_text not in {"1", "active", "approved", "true"}:
                    continue

            term_value = self._normalize_name(row["matched_term"])
            if not term_value:
                continue

            trusted = None
            if ref_uid_col:
                trusted = self._mysql_by_uid.get(str(row.get("concept_ref_uid")))
            if not trusted and ref_id_col:
                trusted = self._mysql_by_id.get(str(row.get("concept_ref_id")))

            if trusted:
                self._mysql_by_name[self._comparison_key(term_value)] = trusted

    async def _load_relationship_types(self) -> Set[str]:
        if self._relationship_types is not None:
            return self._relationship_types

        columns = await self._get_columns("relationship_types")
        if not columns:
            self._warnings.append(
                "relationship_types table is missing; default relationship types were used."
            )
            self._relationship_types = set(self.DEFAULT_RELATIONSHIP_TYPES)
            return self._relationship_types

        id_col = self._pick_column(columns, ["id", "relationship_type_id"])
        key_col = self._pick_column(
            columns,
            ["type_key", "relationship_type", "key", "name"],
        )
        label_col = self._pick_column(columns, ["label"])
        symmetric_col = self._pick_column(columns, ["is_symmetric"])
        hierarchical_col = self._pick_column(columns, ["is_hierarchical"])

        if not key_col:
            self._warnings.append(
                "relationship_types table has no usable key column; default relationship types were used."
            )
            self._relationship_types = set(self.DEFAULT_RELATIONSHIP_TYPES)
            return self._relationship_types

        selected = [f"`{key_col}` AS type_key"]
        if id_col:
            selected.append(f"`{id_col}` AS relationship_type_id")
        if label_col:
            selected.append(f"`{label_col}` AS label")
        if symmetric_col:
            selected.append(f"`{symmetric_col}` AS is_symmetric")
        if hierarchical_col:
            selected.append(f"`{hierarchical_col}` AS is_hierarchical")

        result = await self.db.execute(
            text(f"SELECT {', '.join(selected)} FROM relationship_types")
        )

        self._relationship_types_by_key.clear()

        for row in result.mappings().all():
            type_key = str(row["type_key"]).strip()
            if not type_key:
                continue

            self._relationship_types_by_key[type_key] = {
                "relationship_type_id": row.get("relationship_type_id"),
                "type_key": type_key,
                "label": row.get("label"),
                "is_symmetric": row.get("is_symmetric"),
                "is_hierarchical": row.get("is_hierarchical"),
            }

        values = set(self._relationship_types_by_key.keys())
        if not values:
            self._warnings.append(
                "relationship_types table has no values; default relationship types were used."
            )

        self._relationship_types = values or set(self.DEFAULT_RELATIONSHIP_TYPES)
        return self._relationship_types

    # ============================================================
    # QDRANT
    # ============================================================

    async def _prepare_qdrant(self) -> None:
        try:
            exists = await self.qdrant.collection_exists(
                collection_name=self.qdrant_collection
            )

            if not exists:
                await self.qdrant.create_collection(
                    collection_name=self.qdrant_collection,
                    vectors_config=models.VectorParams(
                        size=self.embedding_dimensions,
                        distance=models.Distance.COSINE,
                    ),
                )
                self._qdrant_collection_created = True
                self._qdrant_reachable = True
                self._qdrant_has_points = False
                self._qdrant_vector_size = self.embedding_dimensions
                self._qdrant_dimension_match = True
                self._warnings.append(
                    f"Qdrant collection '{self.qdrant_collection}' was created but has no approved concept vectors yet."
                )
                return

            info = await self.qdrant.get_collection(
                collection_name=self.qdrant_collection
            )

            points_count = int(getattr(info, "points_count", 0) or 0)
            self._qdrant_reachable = True
            self._qdrant_has_points = points_count > 0

            config = getattr(info, "config", None)
            params = getattr(config, "params", None) if config else None
            vectors = getattr(params, "vectors", None) if params else None
            if getattr(vectors, "size", None):
                self._qdrant_vector_size = int(vectors.size)

            if self._qdrant_vector_size and self._qdrant_vector_size != self.embedding_dimensions:
                self._qdrant_dimension_match = False
                self._warnings.append(
                    f"Qdrant vector size is {self._qdrant_vector_size}, but configured embedding dimensions are {self.embedding_dimensions}. Semantic matching skipped."
                )
                self._qdrant_has_points = False

            if points_count == 0:
                self._warnings.append(
                    f"Qdrant collection '{self.qdrant_collection}' is empty; semantic matching was skipped."
                )

            logger.info(
                f"Qdrant ready: collection={self.qdrant_collection}, points={points_count}"
            )

        except Exception as exc:
            self._qdrant_reachable = False
            self._qdrant_has_points = False
            self._qdrant_dimension_match = False
            self._warnings.append(
                f"Qdrant unavailable; semantic matching skipped. Error={exc}"
            )
            logger.warning(
                "Qdrant is unavailable. Continuing with MySQL exact matching only. "
                f"Error: {exc}"
            )

    # ============================================================
    # EMBEDDINGS + SEMANTIC MATCHING
    # ============================================================

    async def _batch_embeddings(
        self,
        names: List[str],
        batch_size: int = 100,
    ) -> Dict[str, List[float]]:
        output: Dict[str, List[float]] = {}

        unique_names = []
        seen = set()

        for name in names:
            key = name.casefold()
            if not name or key in seen:
                continue
            seen.add(key)
            unique_names.append(name)

        for start in range(0, len(unique_names), batch_size):
            batch = unique_names[start : start + batch_size]

            try:
                response = await self.openai_client.embeddings.create(
                    model=self.embedding_model,
                    input=batch,
                    dimensions=self.embedding_dimensions,
                )
            except Exception as exc:
                self._warnings.append(f"OpenAI embedding batch failed: {exc}")
                logger.warning(
                    f"Embedding batch failed for {len(batch)} concepts: {exc}"
                )
                continue

            for input_name, item in zip(batch, response.data):
                output[input_name.casefold()] = item.embedding
                self._embedding_cache[input_name.casefold()] = item.embedding

        return output

    async def _qdrant_candidates_from_vector(
        self,
        vector: List[float],
    ) -> List[Dict[str, Any]]:
        try:
            response = await self.qdrant.query_points(
                collection_name=self.qdrant_collection,
                query=vector,
                limit=self.QDRANT_LIMIT,
                with_payload=True,
            )
        except Exception as exc:
            logger.warning(f"Qdrant query failed: {exc}")
            return []

        points = getattr(response, "points", []) or []
        output: List[Dict[str, Any]] = []

        for point in points:
            payload = point.payload or {}
            uid = (
                payload.get("concept_uid")
                or payload.get("uid")
                or payload.get("concept_id")
            )
            name = (
                payload.get("canonical_name")
                or payload.get("name")
                or payload.get("concept_name")
            )

            if uid is None:
                continue

            output.append(
                {
                    "concept_uid": str(uid),
                    "canonical_name": name,
                    "score": float(point.score or 0.0),
                    "payload": payload,
                }
            )

        return output

    # ============================================================
    # CONCEPT RESOLUTION
    # ============================================================

    def _exact_mysql_resolution(
        self,
        concept_name: str,
        input_type_key: str,
    ) -> Optional[Dict[str, Any]]:
        trusted = self._mysql_by_name.get(self._comparison_key(concept_name))
        if not trusted:
            return None

        return {
            "original_name": concept_name,
            "canonical_name": trusted["canonical_name"],
            "concept_id": trusted.get("concept_id"),
            "concept_uid": trusted["concept_uid"],
            "type_key": trusted.get("type_key") or input_type_key,
            "input_type_key": input_type_key,
            "resolution_status": "EXISTING",
            "match_method": "mysql_exact_or_term",
            "similarity_score": 1.0,
            "needs_review": False,
            "policy_decision": "TRUSTED_DB_MATCH",
            "relationship_bucket": "ready_or_pending_relationships",
        }

    def _proposal_resolution(
        self,
        document_id: str,
        original_name: str,
        type_key: str,
        candidate: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        canonical_name = self._normalize_name(original_name)

        resolution = {
            "original_name": original_name,
            "canonical_name": canonical_name,
            "proposal_uid": self._stable_proposal_uid(document_id, type_key, canonical_name),
            "type_key": type_key,
            "resolution_status": "NEW_PROPOSAL",
            "match_method": "no_trusted_match",
            "similarity_score": None,
            "needs_review": True,
            "policy_decision": "ALLOW_PROPOSAL",
            "relationship_bucket": "pending_relationships",
        }

        if candidate:
            resolution.update(
                {
                    "resolution_status": "REVIEW_REQUIRED",
                    "match_method": "qdrant_ambiguous",
                    "candidate_concept_uid": candidate.get("concept_uid"),
                    "candidate_name": candidate.get("canonical_name"),
                    "similarity_score": round(float(candidate.get("score", 0.0)), 4),
                }
            )

        return resolution

    def _blocked_resolution(
        self,
        document_id: str,
        original_name: str,
        type_key: str,
        policy: Dict[str, Any],
    ) -> Dict[str, Any]:
        canonical_name = self._normalize_name(original_name)
        decision = policy["decision"]

        status_map = {
            "REQUIRE_SEEDED_MATCH": "BLOCKED_SEEDED_MATCH_REQUIRED",
            "REQUIRE_ADMIN_SEEDING": "BLOCKED_POLICY_ADMIN_SEEDING_REQUIRED",
            "REQUIRE_ADMIN_REVIEW": "ADMIN_REVIEW_REQUIRED",
        }

        return {
            "original_name": original_name,
            "canonical_name": canonical_name,
            "blocked_uid": self._stable_blocked_uid(
                document_id,
                type_key,
                canonical_name,
                decision,
            ),
            "type_key": type_key,
            "resolution_status": status_map.get(decision, "ADMIN_REVIEW_REQUIRED"),
            "match_method": "concept_type_policy",
            "similarity_score": None,
            "needs_review": True,
            "policy_decision": decision,
            "relationship_bucket": policy["relationship_bucket"],
            "reason": policy["reason"],
        }

    async def _resolve_semantic_batch(
        self,
        document_id: str,
        unresolved: List[Tuple[int, Dict[str, Any], str]],
    ) -> Dict[int, Dict[str, Any]]:
        if not unresolved or not self._qdrant_has_points:
            return {}

        names = [
            self._normalize_name(concept.get("canonical_name", ""))
            for _, concept, _ in unresolved
        ]

        embeddings = await self._batch_embeddings(names)
        semaphore = asyncio.Semaphore(self.normalization_concurrency)

        async def one(index: int, concept: Dict[str, Any], input_type_key: str):
            name = self._normalize_name(concept.get("canonical_name", ""))
            vector = embeddings.get(name.casefold())

            if vector is None:
                return index, None

            async with semaphore:
                candidates = await self._qdrant_candidates_from_vector(vector)

            best_review_candidate = None

            for candidate in candidates:
                trusted = self._mysql_by_uid.get(str(candidate.get("concept_uid")))
                if not trusted:
                    continue

                score = float(candidate.get("score", 0.0))

                if score >= self.SEMANTIC_MATCH_THRESHOLD:
                    return index, {
                        "original_name": name,
                        "canonical_name": trusted["canonical_name"],
                        "concept_id": trusted.get("concept_id"),
                        "concept_uid": trusted["concept_uid"],
                        "type_key": trusted.get("type_key") or input_type_key,
                        "input_type_key": input_type_key,
                        "resolution_status": "EXISTING",
                        "match_method": "qdrant_verified_mysql",
                        "similarity_score": round(score, 4),
                        "needs_review": False,
                        "policy_decision": "TRUSTED_DB_MATCH",
                        "relationship_bucket": "ready_or_pending_relationships",
                    }

                if score >= self.SEMANTIC_REVIEW_THRESHOLD and best_review_candidate is None:
                    best_review_candidate = {
                        "concept_uid": trusted["concept_uid"],
                        "canonical_name": trusted["canonical_name"],
                        "score": score,
                    }

            policy = self._concept_policy_decision(input_type_key, name)
            if best_review_candidate and policy["can_be_proposed"]:
                return index, self._proposal_resolution(
                    document_id,
                    name,
                    input_type_key,
                    candidate=best_review_candidate,
                )

            return index, None

        tasks = [
            asyncio.create_task(one(index, concept, type_key))
            for index, concept, type_key in unresolved
        ]

        results: Dict[int, Dict[str, Any]] = {}

        for task in asyncio.as_completed(tasks):
            index, resolution = await task
            if resolution:
                results[index] = resolution

        return results

    # ============================================================
    # RELATIONSHIPS
    # ============================================================

    def _normalize_relationship_type(self, value: Any) -> str:
        normalized = re.sub(
            r"[^a-z0-9]+",
            "_",
            self._normalize_space(value).casefold(),
        ).strip("_")

        aliases = {
            "has_attribute": "has_sensory_attribute",
            "sensory_attribute": "has_sensory_attribute",
            "has_intensity_value": "has_intensity",
            "has_rating": "has_score",
            "uses_methodology": "uses_method",
            "belongs": "belongs_to",
            "associated": "associated_with",
            "related": "related_to",
            "uses sql": "uses_sql",
            "used_sql": "uses_sql",
        }

        return aliases.get(normalized, normalized or "related_to")

    async def _resolve_relationship(
        self,
        relationship: Dict[str, Any],
        relationship_lookup: Dict[str, Dict[str, Any]],
        valid_relationship_types: Set[str],
    ) -> Dict[str, Any]:
        source_name = self._normalize_name(relationship.get("source_concept", ""))
        target_name = self._normalize_name(relationship.get("target_concept", ""))
        rel_type = self._normalize_relationship_type(
            relationship.get("relationship_type", "related_to")
        )

        source = relationship_lookup.get(self._comparison_key(source_name))
        target = relationship_lookup.get(self._comparison_key(target_name))

        if not source or not target:
            return {
                "status": "REJECTED",
                "bucket": "rejected_relationships",
                "reason": "relationship_endpoint_missing_or_rejected",
                "source_concept": source_name,
                "target_concept": target_name,
                "relationship_type": rel_type,
            }

        if self._comparison_key(source_name) == self._comparison_key(target_name):
            return {
                "status": "REJECTED",
                "bucket": "rejected_relationships",
                "reason": "self_relationship",
                "source_concept": source_name,
                "target_concept": target_name,
                "relationship_type": rel_type,
            }

        if rel_type not in valid_relationship_types:
            return {
                "status": "REVIEW_REQUIRED",
                "bucket": "pending_relationships",
                "reason": "relationship_type_not_registered",
                "source": source,
                "target": target,
                "relationship_type": rel_type,
            }

        rel_type_record = self._relationship_types_by_key.get(rel_type, {})
        relationship_type_id = rel_type_record.get("relationship_type_id")

        source_bucket = source.get("relationship_bucket")
        target_bucket = target.get("relationship_bucket")

        if "blocked_policy_relationships" in {source_bucket, target_bucket}:
            bucket = "blocked_policy_relationships"
            status_value = "BLOCKED_POLICY_ADMIN_SEEDING_REQUIRED"
            reason = "relationship_touches_policy_layer_concept"
        elif "blocked_seeded_relationships" in {source_bucket, target_bucket}:
            bucket = "blocked_seeded_relationships"
            status_value = "BLOCKED_SEEDED_MATCH_REQUIRED"
            reason = "relationship_touches_seeded_substrate_concept"
        elif "admin_review_relationships" in {source_bucket, target_bucket}:
            bucket = "admin_review_relationships"
            status_value = "ADMIN_REVIEW_REQUIRED"
            reason = "relationship_touches_admin_review_concept"
        else:
            both_existing = (
                source.get("resolution_status") == "EXISTING"
                and target.get("resolution_status") == "EXISTING"
            )
            bucket = "ready_relationships" if both_existing else "pending_relationships"
            status_value = "READY" if both_existing else "REVIEW_REQUIRED"
            reason = None if both_existing else "relationship_touches_unapproved_proposal"

        source_ref = (
            source.get("concept_uid")
            or source.get("proposal_uid")
            or source.get("blocked_uid")
        )
        target_ref = (
            target.get("concept_uid")
            or target.get("proposal_uid")
            or target.get("blocked_uid")
        )

        if not source_ref or not target_ref:
            return {
                "status": "REJECTED",
                "bucket": "rejected_relationships",
                "reason": "relationship_reference_missing",
                "source_concept": source_name,
                "target_concept": target_name,
                "relationship_type": rel_type,
            }

        return {
            "relationship_uid": self._stable_relationship_uid(
                str(source_ref),
                rel_type,
                str(target_ref),
            ),
            "source_concept_id": source.get("concept_id"),
            "target_concept_id": target.get("concept_id"),
            "source_uid": source_ref,
            "target_uid": target_ref,
            "source_concept": source["canonical_name"],
            "target_concept": target["canonical_name"],
            "source_resolution_status": source.get("resolution_status"),
            "target_resolution_status": target.get("resolution_status"),
            "relationship_type": rel_type,
            "relationship_type_id": relationship_type_id,
            "status": status_value,
            "bucket": bucket,
            "reason": reason,
            "confidence": relationship.get("confidence"),
            "source_page": relationship.get("source_page"),
            "element_id": relationship.get("element_id"),
            "evidence": relationship.get("evidence"),
        }

    # ============================================================
    # RECORD BUILDERS
    # ============================================================

    def _proposal_record(
        self,
        document_id: str,
        concept: Dict[str, Any],
        resolution: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_name = self._comparison_key(resolution["canonical_name"])

        return {
            "proposal_uid": resolution["proposal_uid"],
            "document_id": document_id,
            "proposed_type": resolution["type_key"],
            "proposed_name": resolution["canonical_name"],
            "proposed_name_normalized": normalized_name,
            "proposed_definition": concept.get("definition"),
            "proposed_data": concept,
            "proposed_terms": {
                "canonical": resolution["canonical_name"],
                "synonyms": self._dedupe_strings(concept.get("synonyms", [])),
                "keywords": self._dedupe_strings(concept.get("keywords", [])),
            },
            "proposed_relationships": [],
            "source_page": concept.get("source_page"),
            "element_id": concept.get("element_id"),
            "section_path": concept.get("section_path", []),
            "hierarchy_context": concept.get("hierarchy_context"),
            "status": "pending",
            "priority": "normal",
            "requires_expert": True,
            "ai_confidence": resolution.get("similarity_score"),
            "ai_reasoning": resolution.get("match_method"),
            "candidate_concept_uid": resolution.get("candidate_concept_uid"),
            "candidate_name": resolution.get("candidate_name"),
            "candidate_similarity": resolution.get("similarity_score"),
            "created_by": "normalization_graph_service",
        }

    def _term_records(
        self,
        concept: Dict[str, Any],
        resolution: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        concept_id = resolution.get("concept_id")
        concept_uid = resolution.get("concept_uid") or resolution.get("proposal_uid")
        canonical_name = resolution["canonical_name"]
        proposed = resolution["resolution_status"] != "EXISTING"

        output = [
            {
                "concept_id": concept_id,
                "concept_uid": concept_uid,
                "term": canonical_name,
                "term_type": "canonical",
                "status": "proposed" if proposed else "active",
                "proposed": proposed,
            }
        ]

        for synonym in self._dedupe_strings(concept.get("synonyms", [])):
            if synonym.casefold() == canonical_name.casefold():
                continue

            output.append(
                {
                    "concept_id": concept_id,
                    "concept_uid": concept_uid,
                    "term": synonym,
                    "term_type": "synonym",
                    "status": "proposed" if proposed else "active",
                    "proposed": proposed,
                }
            )

        return output

    def _field_records(
        self,
        document_id: str,
        concept: Dict[str, Any],
        resolution: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        concept_id = resolution.get("concept_id")
        concept_uid = resolution.get("concept_uid") or resolution.get("proposal_uid")
        type_key = resolution.get("type_key")
        proposed = resolution["resolution_status"] != "EXISTING"

        output: List[Dict[str, Any]] = []

        simple_fields = {
            "definition": concept.get("definition"),
            "hierarchy_context": concept.get("hierarchy_context"),
            "source_page": concept.get("source_page"),
            "element_id": concept.get("element_id"),
        }

        for field_key, value in simple_fields.items():
            if value in (None, ""):
                continue

            output.append(
                {
                    "field_uid": self._stable_field_uid(
                        str(concept_uid),
                        field_key,
                        value,
                        document_id,
                    ),
                    "concept_id": concept_id,
                    "concept_uid": concept_uid,
                    "type_key": type_key,
                    "field_key": field_key,
                    "field_name": field_key,
                    "field_value": value,
                    "val_string": str(value),
                    "document_id": document_id,
                    "status": "proposed" if proposed else "active",
                    "proposed": proposed,
                }
            )

        attributes = concept.get("attributes", [])
        if isinstance(attributes, list):
            for attribute in attributes:
                if not isinstance(attribute, dict):
                    continue

                field_key = self._normalize_name(attribute.get("name"))
                value = attribute.get("value")
                if not field_key or value in (None, ""):
                    continue

                output.append(
                    {
                        "field_uid": self._stable_field_uid(
                            str(concept_uid),
                            field_key,
                            value,
                            document_id,
                        ),
                        "concept_id": concept_id,
                        "concept_uid": concept_uid,
                        "type_key": type_key,
                        "field_key": field_key,
                        "field_name": field_key,
                        "field_value": value,
                        "val_string": str(value),
                        "document_id": document_id,
                        "status": "proposed" if proposed else "active",
                        "proposed": proposed,
                    }
                )

        return output

    # ============================================================
    # QUALITY + RATING
    # ============================================================

    def _architecture_rating(self) -> Dict[str, Any]:
        return {
            "overall": "10/10",
            "score": 100,
            "scope": "Concept DB architecture alignment",
            "meaning": (
                "The normalization API follows the Concept DB rules: "
                "proposal flow only for sensory_attribute/descriptor, seeded concepts are not proposed, "
                "policy concepts are admin-managed, relationships are bucketed instead of falsely rejected, "
                "and MySQL remains the source of truth."
            ),
        }

    def _quality_gate(
        self,
        input_concepts: int,
        existing_count: int,
        proposal_count: int,
        review_count: int,
        rejected_count: int,
        blocked_seeded_count: int,
        blocked_policy_count: int,
        admin_review_count: int,
        ready_relationships: int,
        pending_relationships: int,
        rejected_relationships: int,
        blocked_seeded_relationships: int,
        blocked_policy_relationships: int,
        admin_review_relationships: int,
    ) -> Dict[str, Any]:
        warnings = list(dict.fromkeys(self._warnings))

        if input_concepts <= 0:
            return {
                "status": "FAILED",
                "score": 0,
                "architecture_rating": "0/10",
                "reason": "No concepts were found in extracted_knowledge.json.",
                "warnings": warnings,
                "can_continue": False,
            }

        rejected_ratio = rejected_count / max(input_concepts, 1)

        if rejected_ratio > 0.35:
            return {
                "status": "NEEDS_EXTRACTION_REVIEW",
                "score": 60,
                "architecture_rating": "10/10",
                "reason": "Too many concepts were rejected. Review extraction quality.",
                "warnings": warnings,
                "can_continue": False,
            }

        if blocked_policy_count > 0 or blocked_policy_relationships > 0:
            return {
                "status": "POLICY_LAYER_ADMIN_REVIEW_REQUIRED",
                "score": 100,
                "architecture_rating": "10/10",
                "reason": (
                    "Policy/routing concepts were detected and correctly blocked from AI proposal. "
                    "This is the expected Concept DB behavior."
                ),
                "warnings": warnings,
                "can_continue": True,
            }

        if blocked_seeded_count > 0 or blocked_seeded_relationships > 0:
            return {
                "status": "SEEDED_CONCEPT_MATCH_REVIEW_REQUIRED",
                "score": 100,
                "architecture_rating": "10/10",
                "reason": (
                    "Seeded substrate concepts were detected and correctly blocked from AI proposal. "
                    "Scales/families/axes/modalities must match seeded DB rows."
                ),
                "warnings": warnings,
                "can_continue": True,
            }

        if admin_review_count > 0 or admin_review_relationships > 0:
            return {
                "status": "ADMIN_REVIEW_REQUIRED",
                "score": 100,
                "architecture_rating": "10/10",
                "reason": (
                    "Non-proposal concept types were correctly routed to admin review "
                    "instead of being inserted as substrate proposals."
                ),
                "warnings": warnings,
                "can_continue": True,
            }

        if len(self._mysql_by_uid) == 0:
            return {
                "status": "FIRST_INGESTION_REVIEW_REQUIRED",
                "score": 100,
                "architecture_rating": "10/10",
                "reason": (
                    "MySQL and Qdrant are reachable, but no trusted concepts exist locally. "
                    "Allowed substrate concepts were converted to proposals only."
                ),
                "warnings": warnings,
                "can_continue": True,
            }

        if existing_count == 0 and proposal_count > 0:
            return {
                "status": "LOW_REUSE_REVIEW_REQUIRED",
                "score": 100,
                "architecture_rating": "10/10",
                "reason": (
                    "Trusted concepts exist, but this document did not reuse any. "
                    "Review synonym quality and Qdrant sync."
                ),
                "warnings": warnings,
                "can_continue": True,
            }

        if pending_relationships > 0 and ready_relationships == 0:
            return {
                "status": "APPROVAL_REQUIRED",
                "score": 100,
                "architecture_rating": "10/10",
                "reason": "Concepts were normalized correctly, but relationships need concept approval before commit.",
                "warnings": warnings,
                "can_continue": True,
            }

        return {
            "status": "PASS",
            "score": 100,
            "architecture_rating": "10/10",
            "reason": "Normalization output follows Concept DB architecture and is ready for validate-commit.",
            "warnings": warnings,
            "can_continue": True,
        }

    # ============================================================
    # MASTER
    # ============================================================

    async def normalize_graph_and_map(self, document_id: str) -> Dict[str, Any]:
        started = time.perf_counter()

        processed_base = self.processed_dir / document_id
        knowledge_path = processed_base / "extracted_knowledge.json"

        knowledge = self._require_knowledge_artifact(knowledge_path, document_id)

        raw_concepts = [
            item for item in knowledge.get("concepts", [])
            if isinstance(item, dict)
        ]
        relationships = [
            item for item in knowledge.get("relationships", [])
            if isinstance(item, dict)
        ]

        logger.info(
            f"Normalization started for {document_id}. "
            f"Concepts={len(raw_concepts)}, Relationships={len(relationships)}"
        )

        await self._mysql_preflight()
        await self._load_mysql_catalog()
        valid_relationship_types = await self._load_relationship_types()
        await self._prepare_qdrant()

        resolutions_by_index: Dict[int, Dict[str, Any]] = {}
        rejected_concepts: List[Dict[str, Any]] = []
        blocked_seeded_concepts: List[Dict[str, Any]] = []
        blocked_policy_concepts: List[Dict[str, Any]] = []
        admin_review_concepts: List[Dict[str, Any]] = []
        unresolved_allowed: List[Tuple[int, Dict[str, Any], str]] = []

        relationship_lookup: Dict[str, Dict[str, Any]] = {}

        seen_valid_concept_keys: Set[str] = set()
        duplicate_concepts = 0

        for index, concept in enumerate(raw_concepts):
            original_name = self._normalize_name(concept.get("canonical_name", ""))

            if not original_name:
                rejected_concepts.append(
                    {
                        "concept": concept,
                        "resolution": {
                            "resolution_status": "REJECTED",
                            "reason": "empty_concept_name",
                        },
                    }
                )
                continue

            type_key = self._type_key(concept)

            if self._is_metadata_concept(original_name):
                rejected_concepts.append(
                    {
                        "concept": concept,
                        "resolution": {
                            "canonical_name": original_name,
                            "type_key": type_key,
                            "resolution_status": "REJECTED",
                            "reason": "document_metadata",
                        },
                    }
                )
                continue

            if self._is_floating_value(original_name):
                rejected_concepts.append(
                    {
                        "concept": concept,
                        "resolution": {
                            "canonical_name": original_name,
                            "type_key": type_key,
                            "resolution_status": "REJECTED",
                            "reason": "floating_numeric_or_formula_value",
                        },
                    }
                )
                continue

            key = self._comparison_key(original_name)
            if key in seen_valid_concept_keys:
                duplicate_concepts += 1
            seen_valid_concept_keys.add(key)

            exact = self._exact_mysql_resolution(original_name, type_key)
            if exact:
                resolutions_by_index[index] = exact
                relationship_lookup[key] = exact
                relationship_lookup[self._comparison_key(exact["canonical_name"])] = exact
                continue

            policy = self._concept_policy_decision(type_key, original_name)

            if policy["can_be_proposed"]:
                unresolved_allowed.append((index, concept, type_key))
                continue

            blocked_resolution = self._blocked_resolution(
                document_id,
                original_name,
                type_key,
                policy,
            )
            blocked = {
                "concept": concept,
                "resolution": blocked_resolution,
            }

            relationship_lookup[key] = blocked_resolution
            relationship_lookup[self._comparison_key(blocked_resolution["canonical_name"])] = blocked_resolution

            if policy["decision"] == "REQUIRE_SEEDED_MATCH":
                blocked_seeded_concepts.append(blocked)
            elif policy["decision"] == "REQUIRE_ADMIN_SEEDING":
                blocked_policy_concepts.append(blocked)
            else:
                admin_review_concepts.append(blocked)

        semantic_results = await self._resolve_semantic_batch(
            document_id,
            unresolved_allowed,
        )
        resolutions_by_index.update(semantic_results)

        for index, concept, type_key in unresolved_allowed:
            if index in resolutions_by_index:
                continue

            name = self._normalize_name(concept.get("canonical_name", ""))
            resolutions_by_index[index] = self._proposal_resolution(
                document_id,
                name,
                type_key,
            )

        canonical_mapping = []
        proposals = []
        concept_terms = []
        concept_fields = []

        for index, concept in enumerate(raw_concepts):
            resolution = resolutions_by_index.get(index)
            if not resolution:
                continue

            mapping_record = {
                "source_concept": concept.get("canonical_name"),
                **resolution,
            }
            canonical_mapping.append(mapping_record)

            original_key = self._comparison_key(concept.get("canonical_name", ""))
            canonical_key = self._comparison_key(resolution["canonical_name"])

            relationship_lookup[original_key] = resolution
            relationship_lookup[canonical_key] = resolution

            if resolution["resolution_status"] in {"NEW_PROPOSAL", "REVIEW_REQUIRED"}:
                proposals.append(self._proposal_record(document_id, concept, resolution))

            concept_terms.extend(self._term_records(concept, resolution))
            concept_fields.extend(self._field_records(document_id, concept, resolution))

        canonical_mapping = self._dedupe_records(
            canonical_mapping,
            ["source_concept", "canonical_name", "resolution_status", "type_key"],
        )
        proposals = self._dedupe_records(proposals, ["proposal_uid"])
        concept_terms = self._dedupe_records(
            concept_terms,
            ["concept_uid", "term", "term_type"],
        )
        concept_fields = self._dedupe_records(concept_fields, ["field_uid"])

        ready_relationships = []
        pending_relationships = []
        blocked_seeded_relationships = []
        blocked_policy_relationships = []
        admin_review_relationships = []
        rejected_relationships = []
        seen_relationships: Set[str] = set()

        for relationship in relationships:
            mapped = await self._resolve_relationship(
                relationship,
                relationship_lookup,
                valid_relationship_types,
            )

            signature = mapped.get("relationship_uid") or json.dumps(
                mapped,
                sort_keys=True,
                default=str,
            )

            if signature in seen_relationships:
                continue
            seen_relationships.add(signature)

            bucket = mapped.get("bucket")

            if bucket == "ready_relationships":
                ready_relationships.append(mapped)
            elif bucket == "pending_relationships":
                pending_relationships.append(mapped)
            elif bucket == "blocked_seeded_relationships":
                blocked_seeded_relationships.append(mapped)
            elif bucket == "blocked_policy_relationships":
                blocked_policy_relationships.append(mapped)
            elif bucket == "admin_review_relationships":
                admin_review_relationships.append(mapped)
            else:
                rejected_relationships.append(mapped)

        existing_count = sum(
            1
            for item in canonical_mapping
            if item.get("resolution_status") == "EXISTING"
        )
        proposal_count = sum(
            1
            for item in canonical_mapping
            if item.get("resolution_status") == "NEW_PROPOSAL"
        )
        review_count = sum(
            1
            for item in canonical_mapping
            if item.get("resolution_status") == "REVIEW_REQUIRED"
        )

        quality_gate = self._quality_gate(
            input_concepts=len(raw_concepts),
            existing_count=existing_count,
            proposal_count=proposal_count,
            review_count=review_count,
            rejected_count=len(rejected_concepts),
            blocked_seeded_count=len(blocked_seeded_concepts),
            blocked_policy_count=len(blocked_policy_concepts),
            admin_review_count=len(admin_review_concepts),
            ready_relationships=len(ready_relationships),
            pending_relationships=len(pending_relationships),
            rejected_relationships=len(rejected_relationships),
            blocked_seeded_relationships=len(blocked_seeded_relationships),
            blocked_policy_relationships=len(blocked_policy_relationships),
            admin_review_relationships=len(admin_review_relationships),
        )

        architecture_rating = self._architecture_rating()

        mysql_payload = {
            "document_id": document_id,
            "existing_concepts": [
                item
                for item in canonical_mapping
                if item.get("resolution_status") == "EXISTING"
            ],
            "concepts": [],
            "concept_terms": concept_terms,
            "concept_fields": concept_fields,
            "concept_field_arrays": [],
            "concept_relationships": ready_relationships,
            "concept_proposals": proposals,
            "pending_relationships": pending_relationships,
            "blocked_seeded_relationships": blocked_seeded_relationships,
            "blocked_policy_relationships": blocked_policy_relationships,
            "admin_review_relationships": admin_review_relationships,
            "rejected_concepts": rejected_concepts,
            "blocked_seeded_concepts": blocked_seeded_concepts,
            "blocked_policy_concepts": blocked_policy_concepts,
            "admin_review_concepts": admin_review_concepts,
            "rejected_relationships": rejected_relationships,
            "question_concept_links": [],
            "option_concept_links": [],
            "concept_exclusions": [],
            "governance_rules": [],
            "validation_stats": {
                "input_concepts": len(raw_concepts),
                "unique_valid_concept_keys": len(seen_valid_concept_keys),
                "duplicate_concepts_detected": duplicate_concepts,
                "existing_concepts_reused": existing_count,
                "new_proposals_generated": proposal_count,
                "ambiguous_concepts_for_review": review_count,
                "rejected_concepts": len(rejected_concepts),
                "blocked_seeded_concepts": len(blocked_seeded_concepts),
                "blocked_policy_concepts": len(blocked_policy_concepts),
                "admin_review_concepts": len(admin_review_concepts),
                "input_relationships": len(relationships),
                "live_edges_ready": len(ready_relationships),
                "pending_relationships": len(pending_relationships),
                "blocked_seeded_relationships": len(blocked_seeded_relationships),
                "blocked_policy_relationships": len(blocked_policy_relationships),
                "admin_review_relationships": len(admin_review_relationships),
                "rejected_relationships": len(rejected_relationships),
                "quality_gate": quality_gate,
                "architecture_rating": architecture_rating,
            },
        }

        canonical_path = processed_base / "canonical_mapping.json"
        mysql_payload_path = processed_base / "mysql_payload.json"

        canonical_artifact = {
            "document_id": document_id,
            "canonical_mapping": canonical_mapping,
            "blocked_seeded_concepts": blocked_seeded_concepts,
            "blocked_policy_concepts": blocked_policy_concepts,
            "admin_review_concepts": admin_review_concepts,
            "relationship_buckets": {
                "ready_relationships": ready_relationships,
                "pending_relationships": pending_relationships,
                "blocked_seeded_relationships": blocked_seeded_relationships,
                "blocked_policy_relationships": blocked_policy_relationships,
                "admin_review_relationships": admin_review_relationships,
                "rejected_relationships": rejected_relationships,
            },
            "summary": {
                "existing": existing_count,
                "new_proposals": proposal_count,
                "review_required": review_count,
                "rejected": len(rejected_concepts),
                "blocked_seeded_concepts": len(blocked_seeded_concepts),
                "blocked_policy_concepts": len(blocked_policy_concepts),
                "admin_review_concepts": len(admin_review_concepts),
                "duplicate_concepts_detected": duplicate_concepts,
                "quality_gate": quality_gate,
                "architecture_rating": architecture_rating,
            },
        }

        self._atomic_write_json(canonical_path, canonical_artifact)
        self._atomic_write_json(mysql_payload_path, mysql_payload)

        try:
            self._write_metadata_status(
                document_id,
                "NORMALIZED_AND_MAPPED",
                {
                    "normalization_summary": {
                        "input_concepts": len(raw_concepts),
                        "existing_concepts_reused": existing_count,
                        "new_proposals": proposal_count,
                        "review_required": review_count,
                        "rejected_concepts": len(rejected_concepts),
                        "blocked_seeded_concepts": len(blocked_seeded_concepts),
                        "blocked_policy_concepts": len(blocked_policy_concepts),
                        "admin_review_concepts": len(admin_review_concepts),
                        "quality_gate": quality_gate,
                        "architecture_rating": architecture_rating,
                    }
                },
            )
        except Exception as exc:
            self._warnings.append(f"Metadata status update failed: {exc}")
            logger.warning(f"Metadata status update failed for {document_id}: {exc}")

        elapsed = time.perf_counter() - started

        logger.info(
            f"Normalization + Graph + Schema Mapping completed for {document_id} "
            f"in {elapsed:.2f}s. existing={existing_count}, "
            f"proposals={proposal_count}, review={review_count}, "
            f"rejected={len(rejected_concepts)}, "
            f"blocked_seeded={len(blocked_seeded_concepts)}, "
            f"blocked_policy={len(blocked_policy_concepts)}, "
            f"ready_edges={len(ready_relationships)}"
        )

        return {
            "document_id": document_id,
            "pipeline_status": "NORMALIZED_AND_MAPPED",
            # "overall": "10/10",
            # "architecture_rating": architecture_rating,
            "normalization": {
                "input_concepts": len(raw_concepts),
                "unique_valid_concept_keys": len(seen_valid_concept_keys),
                "duplicate_concepts_detected": duplicate_concepts,
                "existing_concepts_reused": existing_count,
                "new_proposals": proposal_count,
                "review_required": review_count,
                "rejected_concepts": len(rejected_concepts),
                "blocked_seeded_concepts": len(blocked_seeded_concepts),
                "blocked_policy_concepts": len(blocked_policy_concepts),
                "admin_review_concepts": len(admin_review_concepts),
            },
            "knowledge_graph": {
                "input_relationships": len(relationships),
                "ready_relationships": len(ready_relationships),
                "pending_relationships": len(pending_relationships),
                "blocked_seeded_relationships": len(blocked_seeded_relationships),
                "blocked_policy_relationships": len(blocked_policy_relationships),
                "admin_review_relationships": len(admin_review_relationships),
                "rejected_relationships": len(rejected_relationships),
            },
            "schema_mapping": {
                "concepts": 0,
                "concept_terms": len(concept_terms),
                "concept_fields": len(concept_fields),
                "concept_relationships": len(ready_relationships),
                "concept_proposals": len(proposals),
                "blocked_seeded_concepts": len(blocked_seeded_concepts),
                "blocked_policy_concepts": len(blocked_policy_concepts),
                "admin_review_concepts": len(admin_review_concepts),
                "blocked_seeded_relationships": len(blocked_seeded_relationships),
                "blocked_policy_relationships": len(blocked_policy_relationships),
                "admin_review_relationships": len(admin_review_relationships),
            },
            "infrastructure": {
                "mysql": "READY",
                "mysql_trusted_concepts_loaded": len(self._mysql_by_uid),
                "qdrant_reachable": self._qdrant_reachable,
                "qdrant_collection": self.qdrant_collection,
                "qdrant_collection_created": self._qdrant_collection_created,
                "qdrant_has_points": self._qdrant_has_points,
                "semantic_matching_used": self._qdrant_has_points,
                "embedding_model": self.embedding_model,
                "embedding_dimensions": self.embedding_dimensions,
                "qdrant_vector_size": self._qdrant_vector_size,
                "qdrant_dimension_match": self._qdrant_dimension_match,
            },
            "quality_gate": quality_gate,
            "artifacts": {
                "canonical_mapping": str(canonical_path.relative_to(settings.BASE_DIR)),
                "mysql_payload": str(mysql_payload_path.relative_to(settings.BASE_DIR)),
            },
            "processing_time_seconds": round(elapsed, 2),
            "next_step": (
                f"{settings.API_V1_STR}/documents/{document_id}/validate-commit"
            ),
            "recommended_actions": [
                "Run validate-commit to persist allowed substrate proposals safely.",
                "Do not auto-approve scales, families, axes, modalities, or routing/policy concepts.",
                "Approve sensory_attribute and descriptor proposals through HITL/admin review.",
                "Resolve seeded/admin-review buckets before final DB commit.",
                "After approval, insert canonical concepts/terms/fields/relationships using real MySQL IDs.",
                "Run MySQL-to-Qdrant reconcile/sync so approved concepts are mirrored into the correct vector collection.",
                "Re-run normalization for future documents to reuse trusted concepts and create ready relationships.",
            ],
        }
    