import json
from pathlib import Path
from app.core.config import settings
from app.core.logger import logger
from app.services.structure_service import StructureService
from app.services.extraction_service import ExtractionService
from app.services.canonical_service import CanonicalService
from app.services.schema_service import SchemaService

class PipelineOrchestrator:
    def __init__(self, document_id: str):
        self.document_id = document_id
        self.raw_dir = settings.STORAGE_RAW_DIR
        self.processed_dir = settings.STORAGE_PROCESSED_DIR
        
        # Instantiate sub-services
        self.structure_service = StructureService()
        self.extraction_service = ExtractionService()
        self.canonical_service = CanonicalService()
        self.schema_service = SchemaService()

    def _update_status(self, status: str, stage: str, progress: int, completed_stages: list, remaining_stages: list):
        """Updates metadata.json with granular progress for the /status API."""
        metadata_path = self.raw_dir / self.document_id / "metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                
                meta["pipeline_status"] = status
                meta["progress"] = progress
                meta["current_stage"] = stage
                meta["completed_stages"] = completed_stages
                meta["remaining_stages"] = remaining_stages
                
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to update metadata status for {self.document_id}: {str(e)}")

    async def run_full_pipeline(self):
        """Executes the complete backend pipeline sequentially in the background."""
        logger.info(f"Starting Master Pipeline Orchestrator for document: {self.document_id}")
        
        stages_flow = [
            ("DOCUMENT_TREE", "Building Logical Document Hierarchy", self._run_structure),
            ("LLM_EXTRACTION", "Extracting Concepts & Rules via LLM", self._run_extraction),
            ("CANONICAL_MAPPING", "Normalizing Concepts via Qdrant", self._run_normalization),
            ("SCHEMA_MAPPING", "Validating Graph & Mapping MySQL Schema", self._run_schema_mapping)
        ]

        completed = ["UPLOAD", "OCR", "IMAGE_EXTRACTION", "TABLE_EXTRACTION"]
        remaining = [s[0] for s in stages_flow]
        total_steps = len(stages_flow)

        try:
            for idx, (stage_key, stage_desc, stage_func) in enumerate(stages_flow, start=1):
                progress = int((idx / total_steps) * 100)
                remaining.remove(stage_key)
                
                self._update_status(
                    status="RUNNING",
                    stage=stage_key,
                    progress=progress,
                    completed_stages=completed,
                    remaining_stages=remaining
                )
                
                logger.info(f"[{self.document_id}] Executing stage: {stage_key} ({stage_desc})")
                await stage_func()
                
                completed.append(stage_key)

            # Final success state
            self._update_status(
                status="READY_FOR_REVIEW",
                stage="COMPLETED",
                progress=100,
                completed_stages=completed,
                remaining_stages=[]
            )
            logger.info(f"Pipeline successfully completed for document: {self.document_id}")

        except Exception as e:
            logger.error(f"Pipeline failed at document {self.document_id}: {str(e)}", exc_info=True)
            self._update_status(
                status="FAILED",
                stage="ERROR",
                progress=0,
                completed_stages=completed,
                remaining_stages=remaining
            )

    async def _run_structure(self):
        await self.structure_service.build_structural_tree(self.document_id)

    async def _run_extraction(self):
        await self.extraction_service.extract_knowledge(self.document_id)

    async def _run_normalization(self):
        await self.canonical_service.normalize_concepts(self.document_id)

    async def _run_schema_mapping(self):
        await self.schema_service.build_mysql_payload(self.document_id)





        