from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Cyber AI Platform"

    HOST: str = "0.0.0.0"

    PORT: int = 8000

    LLAMA_BASE_URL: str = "http://127.0.0.1:8080"

    MODEL_NAME: str = "RavenX"

    # Shared persistence for enterprise engines.
    # Default is SQLite for zero-setup local runs.
    # Point DATABASE_URL at PostgreSQL in .env for real deployments:
    #   postgresql+psycopg://xolaris:xolaris@localhost:5432/xolaris
    DATABASE_URL: str = "sqlite+pysqlite:///./xolaris.db"

    # Create ORM tables on first container init (dev/local).
    # Prefer migrations in production; leave True for local Postgres bring-up.
    CREATE_TABLES: bool = True

    # Decision Service: enable V2 AI stack gateway (set False for deterministic-only).
    DECISION_ENABLE_AI_STACK: bool = False

    # Chat LLMService: wire DecisionEngine → Context → Prompt → ProviderFactory.
    # Set False to use legacy PromptService + LlamaProvider.chat path.
    LLM_ENABLE_V2_STACK: bool = True

    # Scan / Ingest: default mode for chat tools + API when omitted.
    # simulate = sample payloads (no Nuclei binary). live = real adapters.
    SCAN_DEFAULT_MODE: str = "simulate"

    # Enable ScanAwareIntentRouter + ScanToolBuilder inside LLMService.
    SCAN_ENABLE_CHAT_TOOLS: bool = True

    # Stable demo tenant for chat-triggered scans (override in .env).
    SCAN_DEFAULT_TENANT_ID: str = "00000000-0000-4000-8000-000000000001"

    # When chat runs a scan, also chain Trust→Risk→Decision→Planner.
    SCAN_CHAT_RUN_PIPELINE: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
