from pydantic_settings import BaseSettings
from typing import Optional, List


class LLMModel:
    """Класс для представления конфигурации LLM модели"""
    def __init__(self, name: str, api_key: str, model: str, url: str):
        self.name = name
        self.api_key = api_key
        self.model = model
        self.url = url


class Settings(BaseSettings):
    # Database settings
    database_url: str = "postgresql://analyzer_user:analyzer_pass@localhost:5433/query_analyzer"

    # LLM settings (основная модель)
    llm_api_key: str = "your_openai_api_key_here"
    llm_model: str = "gpt-4o"
    llm_url: str = "https://api.openai.com/v1"

    # Дополнительные LLM модели (опциональные)
    llm_api_key_1: Optional[str] = None
    llm_model_1: Optional[str] = None
    llm_url_1: Optional[str] = None

    llm_api_key_2: Optional[str] = None
    llm_model_2: Optional[str] = None
    llm_url_2: Optional[str] = None

    llm_api_key_3: Optional[str] = None
    llm_model_3: Optional[str] = None
    llm_url_3: Optional[str] = None

    llm_api_key_4: Optional[str] = None
    llm_model_4: Optional[str] = None
    llm_url_4: Optional[str] = None

    llm_api_key_5: Optional[str] = None
    llm_model_5: Optional[str] = None
    llm_url_5: Optional[str] = None

    # Application settings
    app_name: str = "PostgreSQL Query Analyzer"
    debug: bool = False
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Analysis settings
    max_query_length: int = 10000
    analysis_timeout: int = 30

    class Config:
        env_file = "../.env"  # .env файл находится в корне проекта
        case_sensitive = False
        extra = "ignore"  # Игнорируем дополнительные поля

    def get_available_models(self) -> List[LLMModel]:
        """Возвращает список всех доступных LLM моделей"""
        models = []

        # Основная модель
        models.append(LLMModel(
            name="Основная модель",
            api_key=self.llm_api_key,
            model=self.llm_model,
            url=self.llm_url
        ))

        # Дополнительные модели
        for i in range(1, 6):
            api_key = getattr(self, f"llm_api_key_{i}", None)
            model = getattr(self, f"llm_model_{i}", None)
            url = getattr(self, f"llm_url_{i}", None)

            if api_key and model and url:
                models.append(LLMModel(
                    name=f"Модель {i}",
                    api_key=api_key,
                    model=model,
                    url=url
                ))

        return models

    def get_model_by_name(self, name: str) -> Optional[LLMModel]:
        """Возвращает модель по имени"""
        models = self.get_available_models()
        for model in models:
            if model.name == name:
                return model
        return None

    def get_model_by_index(self, index: int) -> Optional[LLMModel]:
        """Возвращает модель по индексу"""
        models = self.get_available_models()
        if 0 <= index < len(models):
            return models[index]
        return None


settings = Settings()
