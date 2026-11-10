import os
from pathlib import Path

try:
    from pydantic_settings import BaseSettings
    class _BaseConfig(BaseSettings):
        class Config:
            env_file = ".env"
            extra = "ignore"
except ImportError:
    class _BaseConfig:
        pass

class Settings(_BaseConfig):
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-pro-latest")
    gemini_embedding_model: str = os.getenv("GEMINI_EMBEDDING_MODEL", "models/text-embedding-004")

    otel_service_name: str = os.getenv("OTEL_SERVICE_NAME", "sre-incident-rag-service")
    otel_exporter_otlp_endpoint: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    otel_exporter_otlp_insecure: bool = os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() == "true"
    otel_environment: str = os.getenv("OTEL_ENVIRONMENT", "production")

    base_dir: Path = Path(__file__).resolve().parent.parent
    chroma_persist_directory: str = str(Path(__file__).resolve().parent.parent / "chroma_db")
    chroma_collection_name: str = "sre_incident_knowledge_base"
    sample_data_dir: Path = Path(__file__).resolve().parent.parent / "sample_data"

    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()
