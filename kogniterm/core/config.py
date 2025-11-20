from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # LLM Configuration
    openrouter_api_key: Optional[str] = Field(None, validation_alias="OPENROUTER_API_KEY")
    litellm_model: Optional[str] = Field(None, validation_alias="LITELLM_MODEL")
    litellm_api_base: str = Field("https://openrouter.ai/api/v1", validation_alias="LITELLM_API_BASE")
    
    google_api_key: Optional[str] = Field(None, validation_alias="GOOGLE_API_KEY")
    gemini_model: Optional[str] = Field(None, validation_alias="GEMINI_MODEL")

    # Application Configuration
    max_output_length: int = Field(20000, description="Maximum length of command output before truncation")
    
    # LLM Parameters
    temperature: float = 0.7
    top_p: float = 0.95
    top_k: int = 40
    
    # Limits
    max_conversation_tokens: int = 128000
    max_tool_output_tokens: int = 100000
    max_tool_message_content_length: int = 100000
    summary_max_tokens: int = 1500
    
    # Rate Limiting
    rate_limit_period: int = 60
    rate_limit_calls: int = 20

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
