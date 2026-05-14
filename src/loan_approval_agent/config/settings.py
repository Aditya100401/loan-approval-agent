"""Configuration management using environment variables."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # LLM Provider Settings
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key (or compatible provider)"
    )
    openai_base_url: Optional[str] = Field(
        default="https://api.openai.com/v1",
        description="Base URL for OpenAI-compatible API"
    )
    openai_model: str = Field(
        default="gpt-4o",
        description="Model to use for extraction and decisions"
    )
    
    # UiPath Settings
    uipath_organization_id: Optional[str] = Field(
        default=None,
        description="UiPath organization ID"
    )
    uipath_tenant_id: Optional[str] = Field(
        default=None,
        description="UiPath tenant ID"
    )
    uipath_folder_id: Optional[str] = Field(
        default=None,
        description="UiPath folder ID"
    )
    
    # Context Grounding Settings
    context_grounding_index: str = Field(
        default="loan-policies",
        description="Name of the Context Grounding index for policies"
    )
    
    # Email Settings
    smtp_host: Optional[str] = Field(
        default=None,
        description="SMTP server host"
    )
    smtp_port: int = Field(
        default=587,
        description="SMTP server port"
    )
    smtp_user: Optional[str] = Field(
        default=None,
        description="SMTP username"
    )
    smtp_password: Optional[str] = Field(
        default=None,
        description="SMTP password"
    )
    email_from: Optional[str] = Field(
        default=None,
        description="Sender email address"
    )
    
    # Application Settings
    max_processing_time_seconds: int = Field(
        default=30,
        description="Maximum time allowed for processing"
    )
    hitl_enabled: bool = Field(
        default=True,
        description="Enable Human-in-the-Loop for all decisions"
    )
    hitl_required_for_yellow: bool = Field(
        default=True,
        description="Require HITL for YELLOW decisions"
    )
    hitl_required_for_green: bool = Field(
        default=False,
        description="Require HITL for GREEN decisions"
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
