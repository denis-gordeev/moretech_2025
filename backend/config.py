from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database settings
    database_url: str = "postgresql://analyzer_user:analyzer_pass@localhost:5432/query_analyzer"
    
    # LLM settings
    openai_api_key: str
    openai_model: str = "gpt-4o"
    
    # Custom LLM settings (optional)
    llm_url: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    
    # Application settings
    app_name: str = "PostgreSQL Query Analyzer"
    debug: bool = False
    cors_origins: list = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # Analysis settings
    max_query_length: int = 10000
    analysis_timeout: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
