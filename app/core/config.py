# import os
# from pathlib import Path
# from pydantic_settings import BaseSettings

# class Settings(BaseSettings):
#     APP_NAME: str = "Sensory Knowledge Engineering Platform"
#     API_V1_STR: str = "/api/v1"
#     DEBUG: bool = False
    
#     # Base Directories
#     BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
#     STORAGE_RAW_DIR: Path = BASE_DIR / "storage" / "raw"
#     STORAGE_PROCESSED_DIR: Path = BASE_DIR / "storage" / "processed"
    
#     # File Limits
#     MAX_UPLOAD_SIZE_MB: int = 100
#     ALLOWED_EXTENSIONS: set = {".pdf"}
    
#     # Database & Vector Store Settings
#     MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
#     MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", 3306))
#     MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
#     MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
#     MYSQL_DB: str = os.getenv("MYSQL_DB", "sensory_db")
    
#     QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
#     QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", 6333))
    
#     OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

#     def init_storage(self) -> None:
#         """Ensure storage directory trees exist."""
#         self.STORAGE_RAW_DIR.mkdir(parents=True, exist_ok=True)
#         self.STORAGE_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

#     class Config:
#         env_file = ".env"
#         case_sensitive = True

# settings = Settings()
# settings.init_storage()








from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Sensory Knowledge Engineering Platform"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    
    # Base Directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    STORAGE_RAW_DIR: Path = BASE_DIR / "storage" / "raw"
    STORAGE_PROCESSED_DIR: Path = BASE_DIR / "storage" / "processed"
    
    # File Limits
    MAX_UPLOAD_SIZE_MB: int = 100
    ALLOWED_EXTENSIONS: set = {".pdf"}
    
    # Database & Vector Store Settings (Defaults overridden by .env)
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "ai_keytest"
    
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333

    QDRANT_CONCEPTS_COLLECTION: str = "concepts_3072"
    QDRANT_TERMS_COLLECTION: str = "concept_terms_unified_3072"

    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIMENSION: int = 3072
    QDRANT_SYNC_MAX_CONCEPTS: int = 100
    
    # AI Model Provider
    OPENAI_API_KEY: str = ""

    def init_storage(self) -> None:
        """Ensure storage directory trees exist."""
        self.STORAGE_RAW_DIR.mkdir(parents=True, exist_ok=True)
        self.STORAGE_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Pydantic v2 native .env loader
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
settings.init_storage()