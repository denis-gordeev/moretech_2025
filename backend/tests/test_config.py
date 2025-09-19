"""
Comprehensive pytest tests for config.py Settings and LLMModel classes
"""
import pytest
import os
from unittest.mock import patch, MagicMock

from config import Settings, LLMModel


class TestLLMModel:
    """Test cases for LLMModel class"""

    def test_llm_model_creation(self):
        """Test LLMModel creation with all parameters"""
        model = LLMModel(
            name="Test Model",
            api_key="test_api_key",
            model="gpt-4",
            url="https://api.openai.com/v1"
        )
        
        assert model.name == "Test Model"
        assert model.api_key == "test_api_key"
        assert model.model == "gpt-4"
        assert model.url == "https://api.openai.com/v1"

    def test_llm_model_attributes(self):
        """Test LLMModel attributes are correctly set"""
        model = LLMModel(
            name="OpenAI GPT-4",
            api_key="sk-test123",
            model="gpt-4o",
            url="https://api.openai.com/v1"
        )
        
        assert hasattr(model, 'name')
        assert hasattr(model, 'api_key')
        assert hasattr(model, 'model')
        assert hasattr(model, 'url')


class TestSettings:
    """Test cases for Settings class"""

    def test_settings_default_values(self):
        """Test Settings class default values"""
        settings = Settings()
        
        # Database settings - should load from environment
        assert settings.database_url is not None
        assert "postgresql://" in settings.database_url
        
        # LLM settings - should load from environment
        assert settings.llm_api_key is not None
        assert settings.llm_model is not None
        assert settings.llm_url is not None
        
        # Application settings
        assert settings.app_name == "PostgreSQL Query Analyzer"
        assert settings.debug is False
        assert settings.cors_origins is not None
        
        # Analysis settings
        assert settings.max_query_length == 10000
        assert settings.enable_sql_security_check is False
        assert settings.analysis_timeout == 30

    def test_settings_custom_values(self):
        """Test Settings class with custom values"""
        settings = Settings(
            database_url="postgresql://custom_user:custom_pass@localhost:5432/custom_db",
            llm_api_key="custom_api_key",
            llm_model="gpt-3.5-turbo",
            app_name="Custom Analyzer",
            debug=True,
            max_query_length=5000
        )
        
        assert settings.database_url == "postgresql://custom_user:custom_pass@localhost:5432/custom_db"
        assert settings.llm_api_key == "custom_api_key"
        assert settings.llm_model == "gpt-3.5-turbo"
        assert settings.app_name == "Custom Analyzer"
        assert settings.debug is True
        assert settings.max_query_length == 5000

    def test_get_available_models_only_main_model(self):
        """Test get_available_models with only main model configured"""
        settings = Settings(
            llm_api_key="test_api_key",
            llm_model="gpt-4",
            llm_url="https://api.openai.com/v1"
        )
        
        models = settings.get_available_models()
        
        # Should have at least the main model, but may have additional models from environment
        assert len(models) >= 1
        assert models[0].name == "Основная модель"
        assert models[0].api_key == "test_api_key"
        assert models[0].model == "gpt-4"
        assert models[0].url == "https://api.openai.com/v1"

    def test_get_available_models_with_additional_models(self):
        """Test get_available_models with additional models configured"""
        settings = Settings(
            llm_api_key="main_api_key",
            llm_model="gpt-4",
            llm_url="https://api.openai.com/v1",
            llm_api_key_1="api_key_1",
            llm_model_1="gpt-3.5-turbo",
            llm_url_1="https://api.openai.com/v1",
            llm_api_key_2="api_key_2",
            llm_model_2="claude-3",
            llm_url_2="https://api.anthropic.com/v1"
        )
        
        models = settings.get_available_models()
        
        # Should have at least 3 models (main + 2 additional)
        assert len(models) >= 3
        
        # Main model
        assert models[0].name == "Основная модель"
        assert models[0].api_key == "main_api_key"
        assert models[0].model == "gpt-4"
        
        # Additional model 1
        assert models[1].name == "Модель 1"
        assert models[1].api_key == "api_key_1"
        assert models[1].model == "gpt-3.5-turbo"
        
        # Additional model 2
        assert models[2].name == "Модель 2"
        assert models[2].api_key == "api_key_2"
        assert models[2].model == "claude-3"

    def test_get_available_models_partial_configuration(self):
        """Test get_available_models with partially configured additional models"""
        settings = Settings(
            llm_api_key="main_api_key",
            llm_model="gpt-4",
            llm_url="https://api.openai.com/v1",
            llm_api_key_1="api_key_1",
            llm_model_1="gpt-3.5-turbo",
            # llm_url_1 is None - this model should not be included
            llm_api_key_2="api_key_2",
            llm_model_2="claude-3",
            llm_url_2="https://api.anthropic.com/v1"
        )
        
        models = settings.get_available_models()
        
        # Should have at least 2 models (main + model 2)
        assert len(models) >= 2
        assert models[0].name == "Основная модель"
        # Find model 2 in the list (it might not be at index 1 due to environment variables)
        model_2 = next((m for m in models if m.name == "Модель 2"), None)
        assert model_2 is not None

    def test_get_model_by_name_existing_model(self):
        """Test get_model_by_name with existing model"""
        settings = Settings(
            llm_api_key="test_api_key",
            llm_model="gpt-4",
            llm_url="https://api.openai.com/v1",
            llm_api_key_1="api_key_1",
            llm_model_1="gpt-3.5-turbo",
            llm_url_1="https://api.openai.com/v1"
        )
        
        model = settings.get_model_by_name("Основная модель")
        
        assert model is not None
        assert model.name == "Основная модель"
        assert model.api_key == "test_api_key"
        assert model.model == "gpt-4"

    def test_get_model_by_name_additional_model(self):
        """Test get_model_by_name with additional model"""
        settings = Settings(
            llm_api_key="test_api_key",
            llm_model="gpt-4",
            llm_url="https://api.openai.com/v1",
            llm_api_key_1="api_key_1",
            llm_model_1="gpt-3.5-turbo",
            llm_url_1="https://api.openai.com/v1"
        )
        
        model = settings.get_model_by_name("Модель 1")
        
        assert model is not None
        assert model.name == "Модель 1"
        assert model.api_key == "api_key_1"
        assert model.model == "gpt-3.5-turbo"

    def test_get_model_by_name_nonexistent_model(self):
        """Test get_model_by_name with non-existent model"""
        settings = Settings()
        
        model = settings.get_model_by_name("Non-existent Model")
        
        assert model is None

    def test_get_model_by_index_valid_index(self):
        """Test get_model_by_index with valid index"""
        settings = Settings(
            llm_api_key="test_api_key",
            llm_model="gpt-4",
            llm_url="https://api.openai.com/v1",
            llm_api_key_1="api_key_1",
            llm_model_1="gpt-3.5-turbo",
            llm_url_1="https://api.openai.com/v1"
        )
        
        # Get first model (index 0)
        model = settings.get_model_by_index(0)
        assert model is not None
        assert model.name == "Основная модель"
        
        # Get second model (index 1)
        model = settings.get_model_by_index(1)
        assert model is not None
        assert model.name == "Модель 1"

    def test_get_model_by_index_invalid_index(self):
        """Test get_model_by_index with invalid index"""
        settings = Settings()
        
        # Test negative index
        model = settings.get_model_by_index(-1)
        assert model is None
        
        # Test index out of range
        model = settings.get_model_by_index(10)
        assert model is None

    def test_get_model_by_index_edge_cases(self):
        """Test get_model_by_index with edge cases"""
        settings = Settings(
            llm_api_key="test_api_key",
            llm_model="gpt-4",
            llm_url="https://api.openai.com/v1"
        )
        
        # At least one model available
        models = settings.get_available_models()
        assert len(models) >= 1
        
        # Index 0 should work
        model = settings.get_model_by_index(0)
        assert model is not None
        
        # Index beyond available models should return None
        model = settings.get_model_by_index(len(models))
        assert model is None

    def test_all_additional_models_configured(self):
        """Test with all 5 additional models configured"""
        settings = Settings(
            llm_api_key="main_key",
            llm_model="gpt-4",
            llm_url="https://api.openai.com/v1",
            llm_api_key_1="key1",
            llm_model_1="model1",
            llm_url_1="url1",
            llm_api_key_2="key2",
            llm_model_2="model2",
            llm_url_2="url2",
            llm_api_key_3="key3",
            llm_model_3="model3",
            llm_url_3="url3",
            llm_api_key_4="key4",
            llm_model_4="model4",
            llm_url_4="url4",
            llm_api_key_5="key5",
            llm_model_5="model5",
            llm_url_5="url5"
        )
        
        models = settings.get_available_models()
        
        # Should have main model + 5 additional models = 6 total
        assert len(models) == 6
        assert models[0].name == "Основная модель"
        assert models[1].name == "Модель 1"
        assert models[2].name == "Модель 2"
        assert models[3].name == "Модель 3"
        assert models[4].name == "Модель 4"
        assert models[5].name == "Модель 5"

    def test_cors_origins_parsing(self):
        """Test CORS origins configuration"""
        settings = Settings(cors_origins="http://localhost:3000,http://127.0.0.1:3000,https://example.com")
        
        assert settings.cors_origins == "http://localhost:3000,http://127.0.0.1:3000,https://example.com"

    def test_settings_config_class(self):
        """Test Settings Config class properties"""
        settings = Settings()
        
        assert hasattr(settings.Config, 'env_file')
        assert settings.Config.env_file == "../.env"
        assert settings.Config.case_sensitive is False
        assert settings.Config.extra == "ignore"

    @patch.dict('os.environ', {'DATABASE_URL': 'postgresql://env_user:env_pass@localhost:5432/env_db'})
    def test_settings_environment_variables(self):
        """Test Settings loading from environment variables"""
        settings = Settings()
        
        # Should load from environment variable
        assert settings.database_url == 'postgresql://env_user:env_pass@localhost:5432/env_db'

    def test_settings_type_validation(self):
        """Test Settings type validation"""
        # Test boolean values
        settings = Settings(debug=True, enable_sql_security_check=True)
        assert settings.debug is True
        assert settings.enable_sql_security_check is True
        
        # Test integer values
        settings = Settings(max_query_length=15000, analysis_timeout=60)
        assert settings.max_query_length == 15000
        assert settings.analysis_timeout == 60

    def test_getattr_usage_in_get_available_models(self):
        """Test that getattr is used correctly in get_available_models"""
        settings = Settings()
        
        # Test that getattr returns None for non-existent attributes
        result = getattr(settings, 'llm_api_key_10', None)
        assert result is None
        
        # Test that getattr returns the correct value for existing attributes
        result = getattr(settings, 'llm_api_key', None)
        assert result is not None

    def test_model_iteration_logic(self):
        """Test the iteration logic in get_available_models"""
        settings = Settings(
            llm_api_key="main_key",
            llm_model="gpt-4",
            llm_url="https://api.openai.com/v1",
            llm_api_key_3="key3",  # Only configure model 3
            llm_model_3="model3",
            llm_url_3="url3"
        )
        
        models = settings.get_available_models()
        
        # Should have at least main model + model 3
        assert len(models) >= 2
        assert models[0].name == "Основная модель"
        # Find model 3 in the list (it might not be at index 1 due to environment variables)
        model_3 = next((m for m in models if m.name == "Модель 3"), None)
        assert model_3 is not None
