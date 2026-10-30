
##############################################################################
# config/settings.py
#
# PURPOSE:
#   Central configuration management for MOSAIC.
#
# STORAGE:
#   SQLite  -> Signals and HITL reviews
#   ChromaDB -> Episodic, semantic and procedural memory
#
# LLM:
#   Groq / OpenAI-compatible embedding configuration
##############################################################################

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """
    All MOSAIC configuration defined in one place.

    Pydantic automatically reads values from environment variables
    and the .env file.

    Environment variable names are case-insensitive.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ----------------------------------------------------------------------
    # OPENAI / EMBEDDINGS
    # ----------------------------------------------------------------------

    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI model used to generate vector embeddings",
    )

    # ----------------------------------------------------------------------
    # LANGSMITH
    # ----------------------------------------------------------------------

    langsmith_api_key: str = Field(
        default="",
        description="Optional LangSmith API key",
    )

    langsmith_project: str = Field(
        default="clinical_trial_intelligence",
        description="LangSmith project name",
    )

    langsmith_tracing_v2: bool = Field(
        default=False,
        description="Enable LangSmith tracing",
    )

    # ----------------------------------------------------------------------
    # GROQ
    # ----------------------------------------------------------------------

    groq_api_key: str = Field(
        default="",
        description="Groq API key for LLM calls",
    )

    groq_chat_model: str = Field(
        default="openai/gpt-oss-20b",
        description="Groq model used for agent reasoning",
    )

    # ----------------------------------------------------------------------
    # GCP
    # ----------------------------------------------------------------------

    gcp_project_id: str = Field(
        default="",
        description="Google Cloud Project ID",
    )

    gcp_region: str = Field(
        default="",
        description="GCP region",
    )

    gcs_bucket_name: str = Field(
        default="",
        description="Google Cloud Storage bucket name",
    )

    # ----------------------------------------------------------------------
    # CLINICALTRIALS.GOV
    # ----------------------------------------------------------------------

    clinical_trials_base_url: str = Field(
        default="https://clinicaltrials.gov/api/v2",
        description="ClinicalTrials.gov API V2 base URL",
    )

    clinical_trials_page_size: int = Field(
        default=100,
        description="Number of studies to fetch per API page",
    )

    # ----------------------------------------------------------------------
    # PUBMED
    # ----------------------------------------------------------------------

    pubmed_base_url: str = Field(
        default="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        description="PubMed E-utilities API base URL",
    )

    # ----------------------------------------------------------------------
    # API SERVER
    # ----------------------------------------------------------------------

    api_host: str = Field(
        default="0.0.0.0",
        description="FastAPI host address",
    )

    api_port: int = Field(
        default=8000,
        description="FastAPI server port",
    )

    api_env: str = Field(
        default="development",
        description="Environment: development or production",
    )

    # ----------------------------------------------------------------------
    # COMPUTED PROPERTIES
    # ----------------------------------------------------------------------

    @property
    def is_production(self) -> bool:
        """Returns True if the application runs in production."""

        return self.api_env.lower() == "production"


# --------------------------------------------------------------------------
# SINGLETON SETTINGS INSTANCE
# --------------------------------------------------------------------------

settings = Settings()
