from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    app_name: str = "Vylix API"
    environment: str = "development"
    port: int = Field(default=4000)
    api_prefix: str = "/api/v1"

    # Database
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/vylix"
    )
    direct_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/vylix"
    )

    # Redis — rate-limiting & caching (separate from Celery to prevent eviction)
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Celery — broker and result backend (isolated DBs, can't evict rate-limit keys)
    celery_broker_url: str = Field(default="redis://localhost:6379/2")
    celery_result_backend: str = Field(default="redis://localhost:6379/1")

    # CORS
    cors_origins: str = Field(default="http://localhost:3000,https://vylix.vercel.app")

    # Uploads
    max_upload_mb: int = Field(default=50, ge=1)
    upload_dir: Path = Field(default=Path("./storage/uploads"))
    temp_dir: Path = Field(default=Path("./tmp"))

    # Storage Provider: "supabase" or "appwrite"
    storage_provider: str = Field(default="supabase")

    # Supabase
    supabase_url: str = Field(default="")
    supabase_service_role_key: str = Field(default="")
    supabase_storage_bucket: str = Field(default="materials")
    supabase_avatars_bucket: str = Field(default="avatars")
    supabase_jwt_secret: str = Field(default="")

    # Appwrite
    appwrite_endpoint: str = Field(default="")
    appwrite_project_id: str = Field(default="")
    appwrite_api_key: str = Field(default="")
    appwrite_storage_bucket_id: str = Field(default="")

    # Study points (referrals / PQ uploads / redemption)
    points_weekly_earn_cap: int = Field(default=300, ge=1)
    points_expiry_days: int = Field(default=90, ge=1)
    max_referees_per_referrer: int = Field(default=5, ge=1)

    # AI
    gemini_api_key: str | None = Field(default=None)
    # Gate the expensive Pro model; false forces every agent call onto Flash-Lite.
    pro_tier_enabled: bool = Field(default=True)

    # Vector search
    # "auto" uses pgvector when GEMINI_API_KEY is set, otherwise ChromaDB.
    # Explicit "pgvector" or "chromadb" forces the backend.
    vector_store_backend: str = Field(default="auto")
    embedding_model: str = Field(default="gemini-embedding-001")
    embedding_dimensions: int = Field(default=768)
    embedding_batch_size: int = Field(default=64)
    embedding_cache_ttl_seconds: int = Field(default=604800)

    # Exact-match response cache for the academic agent (whole-class dedup).
    prompt_cache_ttl_seconds: int = Field(default=604800)

    # Maintenance
    maintenance_api_key: str = Field(default="")

    # Google Drive
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")
    google_redirect_uri: str = Field(default="http://localhost:4000/api/v1/google-drive/callback")
    frontend_url: str = Field(default="http://localhost:3000")

    # Paystack
    paystack_secret_key: str = Field(default="")
    paystack_public_key: str = Field(default="")

    # Worker
    materials_worker_concurrency: int = Field(default=5)

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
