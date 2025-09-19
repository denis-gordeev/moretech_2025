"""
Comprehensive pytest tests for ExampleGenerator class
"""
import pytest
import json
import tempfile
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

from example_generator import ExampleGenerator, ExampleGenerationResponse, ExampleQuery


class TestExampleQuery:
    """Test cases for ExampleQuery model"""

    def test_example_query_creation(self):
        """Test ExampleQuery creation"""
        example = ExampleQuery(
            name="Test Query",
            query="SELECT * FROM users WHERE id = 1",
            description="Simple test query",
            category="simple",
            difficulty="easy"
        )
        
        assert example.name == "Test Query"
        assert example.query == "SELECT * FROM users WHERE id = 1"
        assert example.description == "Simple test query"
        assert example.category == "simple"
        assert example.difficulty == "easy"


class TestExampleGenerationResponse:
    """Test cases for ExampleGenerationResponse model"""

    def test_example_generation_response_creation(self):
        """Test ExampleGenerationResponse creation"""
        examples = [
            ExampleQuery(
                name="Test Query 1",
                query="SELECT * FROM users WHERE id = 1",
                description="Simple test query",
                category="simple",
                difficulty="easy"
            ),
            ExampleQuery(
                name="Test Query 2",
                query="SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id",
                description="JOIN test query",
                category="join",
                difficulty="medium"
            )
        ]
        
        response = ExampleGenerationResponse(examples=examples)
        
        assert len(response.examples) == 2
        assert response.examples[0].name == "Test Query 1"
        assert response.examples[1].name == "Test Query 2"


class TestExampleGenerator:
    """Test cases for ExampleGenerator class"""

    @pytest.fixture
    def temp_test_queries_file(self):
        """Create temporary test queries file for testing"""
        test_queries = {
            "test_queries": [
                {
                    "name": "Test Query 1",
                    "query": "SELECT * FROM users WHERE id = 1",
                    "description": "Simple test query"
                },
                {
                    "name": "Test Query 2", 
                    "query": "SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id",
                    "description": "JOIN test query"
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_queries, f)
            temp_file = Path(f.name)
        
        yield temp_file
        
        # Cleanup
        if temp_file.exists():
            temp_file.unlink()

    @pytest.fixture
    def generator(self):
        """Create ExampleGenerator instance for testing"""
        with patch('example_generator.PostgreSQLAnalyzer') as mock_db, \
             patch('example_generator.LLMAnalyzer') as mock_llm:
            
            mock_db_instance = AsyncMock()
            mock_llm_instance = AsyncMock()
            mock_db.return_value = mock_db_instance
            mock_llm.return_value = mock_llm_instance
            
            generator = ExampleGenerator()
            generator.db_analyzer = mock_db_instance
            generator.llm_analyzer = mock_llm_instance
            
            return generator

    def test_generator_initialization(self):
        """Test ExampleGenerator initialization"""
        with patch('example_generator.PostgreSQLAnalyzer') as mock_db, \
             patch('example_generator.LLMAnalyzer') as mock_llm:
            
            generator = ExampleGenerator()
            
            assert generator.db_analyzer is not None
            assert generator.llm_analyzer is not None
            assert generator._adapted_examples_cache == {}

    @pytest.mark.asyncio
    async def test_get_database_structure_success(self, generator):
        """Test successful database structure retrieval"""
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = [
            {
                "table_name": "users",
                "table_type": "BASE TABLE",
                "column_name": "id",
                "data_type": "integer",
                "is_nullable": "NO",
                "column_default": "nextval('users_id_seq'::regclass)",
                "character_maximum_length": None,
                "is_primary_key": True,
                "is_foreign_key": False,
                "foreign_table_name": None,
                "foreign_column_name": None
            },
            {
                "table_name": "users",
                "table_type": "BASE TABLE",
                "column_name": "name",
                "data_type": "character varying",
                "is_nullable": "YES",
                "column_default": None,
                "character_maximum_length": 255,
                "is_primary_key": False,
                "is_foreign_key": False,
                "foreign_table_name": None,
                "foreign_column_name": None
            }
        ]
        
        generator.db_analyzer.get_connection.return_value.__aenter__.return_value = mock_connection
        generator.db_analyzer.get_database_info = AsyncMock(return_value={"version": "PostgreSQL 15.0"})
        
        result = await generator._get_database_structure()
        
        assert "tables" in result
        assert "total_tables" in result
        assert "database_info" in result
        assert len(result["tables"]) > 0

    @pytest.mark.asyncio
    async def test_get_database_structure_error(self, generator):
        """Test database structure retrieval with error"""
        generator.db_analyzer.get_connection.side_effect = Exception("Database error")
        
        result = await generator._get_database_structure()
        
        assert result["tables"] == []
        assert result["total_tables"] == 0
        assert result["database_info"] == {}

    @pytest.mark.asyncio
    async def test_get_database_structure_for_analyzer_success(self, generator):
        """Test database structure retrieval for specific analyzer"""
        mock_analyzer = AsyncMock()
        mock_connection = AsyncMock()
        mock_connection.fetch.return_value = [
            {
                "table_name": "products",
                "table_type": "BASE TABLE",
                "column_name": "id",
                "data_type": "integer",
                "is_nullable": "NO",
                "column_default": None,
                "character_maximum_length": None,
                "is_primary_key": True,
                "is_foreign_key": False,
                "foreign_table_name": None,
                "foreign_column_name": None
            }
        ]
        
        mock_analyzer.get_connection.return_value.__aenter__.return_value = mock_connection
        mock_analyzer.get_database_info = AsyncMock(return_value={"version": "PostgreSQL 15.0"})
        
        result = await generator._get_database_structure_for_analyzer(mock_analyzer)
        
        assert "tables" in result
        assert "indexes" in result
        assert "constraints" in result
        assert "total_tables" in result
        assert "database_info" in result

    @pytest.mark.asyncio
    async def test_get_database_structure_for_analyzer_error(self, generator):
        """Test database structure retrieval for analyzer with error"""
        mock_analyzer = AsyncMock()
        mock_analyzer.get_connection.side_effect = Exception("Database error")
        
        result = await generator._get_database_structure_for_analyzer(mock_analyzer)
        
        assert result["tables"] == []
        assert result["indexes"] == []
        assert result["constraints"] == []
        assert result["total_tables"] == 0
        assert result["database_info"] == {}

    @pytest.mark.asyncio
    async def test_load_existing_examples_success(self, generator, temp_test_queries_file):
        """Test successful loading of existing examples"""
        with patch('example_generator.Path') as mock_path:
            mock_path.return_value.parent.parent = temp_test_queries_file.parent
            mock_path.return_value.parent = temp_test_queries_file.parent
            mock_path.return_value = temp_test_queries_file
            mock_path.return_value.exists.return_value = True
            
            examples = await generator._load_existing_examples()
            
            assert len(examples) == 2
            assert examples[0]["name"] == "Test Query 1"
            assert examples[1]["name"] == "Test Query 2"

    @pytest.mark.asyncio
    async def test_load_existing_examples_file_not_found(self, generator):
        """Test loading existing examples when file doesn't exist"""
        with patch('example_generator.Path') as mock_path:
            mock_path.return_value.exists.return_value = False
            
            examples = await generator._load_existing_examples()
            
            assert examples == []

    @pytest.mark.asyncio
    async def test_load_existing_examples_invalid_json(self, generator):
        """Test loading existing examples with invalid JSON"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            temp_file = Path(f.name)
        
        try:
            with patch('example_generator.Path') as mock_path:
                mock_path.return_value.parent.parent = temp_file.parent
                mock_path.return_value.parent = temp_file.parent
                mock_path.return_value = temp_file
                mock_path.return_value.exists.return_value = True
                
                examples = await generator._load_existing_examples()
                
                assert examples == []
        finally:
            if temp_file.exists():
                temp_file.unlink()

    @pytest.mark.asyncio
    async def test_generate_examples_with_llm_success(self, generator):
        """Test successful example generation with LLM"""
        # Mock database structure
        db_structure = {
            "tables": [
                {
                    "table_name": "users",
                    "table_type": "BASE TABLE",
                    "columns": [
                        {
                            "name": "id",
                            "type": "integer",
                            "is_primary_key": True,
                            "is_foreign_key": False,
                            "nullable": False
                        },
                        {
                            "name": "name",
                            "type": "character varying",
                            "is_primary_key": False,
                            "is_foreign_key": False,
                            "nullable": True
                        }
                    ],
                    "indexes": [],
                    "stats": {"live_tuples": 1000}
                }
            ],
            "total_tables": 1,
            "database_info": {"version": "PostgreSQL 15.0"}
        }
        
        existing_examples = [
            {
                "name": "Simple Query",
                "query": "SELECT * FROM users WHERE id = 1",
                "description": "Simple test query"
            }
        ]
        
        # Mock LLM response
        mock_llm_response = ExampleGenerationResponse(
            examples=[
                ExampleQuery(
                    name="Generated Query 1",
                    query="SELECT name FROM users WHERE id > 100",
                    description="Generated query for testing",
                    category="simple",
                    difficulty="easy"
                )
            ]
        )
        
        generator.llm_analyzer.client.beta.chat.completions.parse = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=MagicMock(parsed=mock_llm_response))])
        )
        
        with patch.object(generator, '_get_database_structure', return_value=db_structure), \
             patch.object(generator, '_load_existing_examples', return_value=existing_examples):
            
            result = await generator.generate_examples_with_llm()
            
            assert len(result) == 1
            assert result[0]["name"] == "Generated Query 1"
            assert result[0]["query"] == "SELECT name FROM users WHERE id > 100"

    @pytest.mark.asyncio
    async def test_generate_examples_with_llm_error(self, generator):
        """Test example generation with LLM error"""
        with patch.object(generator, '_get_database_structure', side_effect=Exception("Database error")):
            result = await generator.generate_examples_with_llm()
            
            assert result == []

    @pytest.mark.asyncio
    async def test_adapt_examples_to_database_schema_success(self, generator):
        """Test successful adaptation of examples to database schema"""
        template_examples = [
            {
                "name": "User Query",
                "query": "SELECT * FROM users WHERE id = 1",
                "description": "Query for users table"
            }
        ]
        
        db_structure = {
            "tables": [
                {
                    "name": "customers",
                    "type": "BASE TABLE",
                    "columns": [
                        {
                            "name": "customer_id",
                            "type": "integer",
                            "is_primary_key": True,
                            "is_foreign_key": False,
                            "foreign_table": None,
                            "foreign_column": None
                        },
                        {
                            "name": "customer_name",
                            "type": "character varying",
                            "is_primary_key": False,
                            "is_foreign_key": False,
                            "foreign_table": None,
                            "foreign_column": None
                        }
                    ]
                }
            ]
        }
        
        # Mock LLM response
        mock_llm_response = ExampleGenerationResponse(
            examples=[
                ExampleQuery(
                    name="Customer Query",
                    query="SELECT * FROM customers WHERE customer_id = 1",
                    description="Query for customers table",
                    category="adapted",
                    difficulty="medium"
                )
            ]
        )
        
        generator.llm_analyzer.client.beta.chat.completions.parse = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=MagicMock(parsed=mock_llm_response))])
        )
        
        result = await generator._adapt_examples_to_database_schema(template_examples, db_structure)
        
        assert len(result) == 1
        assert result[0]["name"] == "Customer Query"
        assert result[0]["query"] == "SELECT * FROM customers WHERE customer_id = 1"
        assert result[0]["category"] == "adapted"

    @pytest.mark.asyncio
    async def test_adapt_examples_to_database_schema_parsing_error(self, generator):
        """Test adaptation with LLM parsing error"""
        template_examples = [{"name": "Test", "query": "SELECT 1", "description": "Test"}]
        db_structure = {"tables": []}
        
        # Mock LLM response with parsing error
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.parsed = None
        mock_response.choices[0].message.content = '{"examples": [{"name": "Test", "query": "SELECT 1", "description": "Test", "category": "simple", "difficulty": "easy"}]}'
        
        generator.llm_analyzer.client.beta.chat.completions.parse = AsyncMock(return_value=mock_response)
        
        result = await generator._adapt_examples_to_database_schema(template_examples, db_structure)
        
        assert len(result) == 1
        assert result[0]["name"] == "Test"

    @pytest.mark.asyncio
    async def test_adapt_examples_to_database_schema_error(self, generator):
        """Test adaptation with error"""
        template_examples = [{"name": "Test", "query": "SELECT 1", "description": "Test"}]
        db_structure = {"tables": []}
        
        generator.llm_analyzer.client.beta.chat.completions.parse = AsyncMock(
            side_effect=Exception("LLM error")
        )
        
        result = await generator._adapt_examples_to_database_schema(template_examples, db_structure)
        
        assert result == []

    def test_create_adaptation_prompt(self, generator):
        """Test adaptation prompt creation"""
        template_examples = [
            {
                "name": "User Query",
                "query": "SELECT * FROM users WHERE id = 1",
                "description": "Query for users table"
            }
        ]
        
        db_structure = {
            "tables": [
                {
                    "name": "customers",
                    "type": "BASE TABLE",
                    "columns": [
                        {
                            "name": "customer_id",
                            "type": "integer",
                            "is_primary_key": True,
                            "is_foreign_key": False,
                            "foreign_table": None,
                            "foreign_column": None
                        }
                    ]
                }
            ]
        }
        
        prompt = generator._create_adaptation_prompt(template_examples, db_structure)
        
        assert "Адаптируй SQL примеры под новую схему БД" in prompt
        assert "Таблица: customers" in prompt
        assert "customer_id (integer) [PRIMARY KEY]" in prompt
        assert "User Query" in prompt
        assert "SELECT * FROM users WHERE id = 1" in prompt

    def test_create_example_generation_prompt(self, generator):
        """Test example generation prompt creation"""
        db_structure = {
            "tables": [
                {
                    "table_name": "users",
                    "table_type": "BASE TABLE",
                    "columns": [
                        {
                            "name": "id",
                            "type": "integer",
                            "is_primary_key": True,
                            "is_foreign_key": False,
                            "nullable": False
                        }
                    ],
                    "indexes": [],
                    "stats": {"live_tuples": 1000}
                }
            ]
        }
        
        existing_examples = [
            {
                "name": "Simple Query",
                "query": "SELECT * FROM users WHERE id = 1",
                "description": "Simple test query"
            }
        ]
        
        prompt = generator._create_example_generation_prompt(db_structure, existing_examples)
        
        assert "СТРУКТУРА БАЗЫ ДАННЫХ:" in prompt
        assert "Таблица: users" in prompt
        assert "id (integer) [PRIMARY KEY] [NOT NULL]" in prompt
        assert "СУЩЕСТВУЮЩИЕ ПРИМЕРЫ ЗАПРОСОВ:" in prompt
        assert "Simple Query" in prompt

    @pytest.mark.asyncio
    async def test_generate_examples_with_llm_for_database_success(self, generator):
        """Test successful example generation for specific database"""
        mock_analyzer = AsyncMock()
        database_profile_id = "test_profile"
        
        # Mock cache hit
        generator._adapted_examples_cache = {
            database_profile_id: [
                {
                    "name": "Cached Query",
                    "query": "SELECT * FROM cached_table",
                    "description": "Cached query",
                    "category": "cached",
                    "difficulty": "easy"
                }
            ]
        }
        
        result = await generator.generate_examples_with_llm_for_database(mock_analyzer, database_profile_id)
        
        assert len(result) == 1
        assert result[0]["name"] == "Cached Query"

    @pytest.mark.asyncio
    async def test_generate_examples_with_llm_for_database_cache_miss(self, generator):
        """Test example generation for database with cache miss"""
        mock_analyzer = AsyncMock()
        database_profile_id = "test_profile"
        
        # Mock database structure
        db_structure = {
            "tables": [
                {
                    "name": "products",
                    "type": "BASE TABLE",
                    "columns": [
                        {
                            "name": "id",
                            "type": "integer",
                            "is_primary_key": True,
                            "is_foreign_key": False,
                            "foreign_table": None,
                            "foreign_column": None
                        }
                    ]
                }
            ]
        }
        
        template_examples = [
            {
                "name": "Template Query",
                "query": "SELECT * FROM template_table",
                "description": "Template query"
            }
        ]
        
        # Mock LLM response
        mock_llm_response = ExampleGenerationResponse(
            examples=[
                ExampleQuery(
                    name="Adapted Query",
                    query="SELECT * FROM products WHERE id = 1",
                    description="Adapted query",
                    category="adapted",
                    difficulty="medium"
                )
            ]
        )
        
        generator.llm_analyzer.client.beta.chat.completions.parse = AsyncMock(
            return_value=MagicMock(choices=[MagicMock(message=MagicMock(parsed=mock_llm_response))])
        )
        
        with patch.object(generator, '_get_database_structure_for_analyzer', return_value=db_structure), \
             patch.object(generator, '_load_existing_examples', return_value=template_examples):
            
            result = await generator.generate_examples_with_llm_for_database(mock_analyzer, database_profile_id)
            
            assert len(result) == 1
            assert result[0]["name"] == "Adapted Query"
            assert database_profile_id in generator._adapted_examples_cache

    @pytest.mark.asyncio
    async def test_merge_and_save_examples_success(self, generator, temp_test_queries_file):
        """Test successful merging and saving of examples"""
        existing_examples = [
            {
                "name": "Existing Query",
                "query": "SELECT * FROM existing_table",
                "description": "Existing query"
            }
        ]
        
        new_examples = [
            {
                "name": "New Query",
                "query": "SELECT * FROM new_table",
                "description": "New query",
                "category": "new",
                "difficulty": "medium"
            }
        ]
        
        with patch.object(generator, '_load_existing_examples', return_value=existing_examples), \
             patch.object(generator, 'generate_examples_with_llm', return_value=new_examples), \
             patch('example_generator.Path') as mock_path:
            
            mock_path.return_value.parent.parent = temp_test_queries_file.parent
            
            result = await generator.merge_and_save_examples()
            
            assert len(result) == 2
            assert result[0]["name"] == "Existing Query"
            assert result[1]["name"] == "New Query"

    @pytest.mark.asyncio
    async def test_merge_and_save_examples_duplicate_handling(self, generator, temp_test_queries_file):
        """Test merging with duplicate query handling"""
        existing_examples = [
            {
                "name": "Existing Query",
                "query": "SELECT * FROM existing_table",
                "description": "Existing query"
            }
        ]
        
        new_examples = [
            {
                "name": "Duplicate Query",
                "query": "SELECT * FROM existing_table",  # Same query
                "description": "Duplicate query",
                "category": "duplicate",
                "difficulty": "easy"
            },
            {
                "name": "New Query",
                "query": "SELECT * FROM new_table",
                "description": "New query",
                "category": "new",
                "difficulty": "medium"
            }
        ]
        
        with patch.object(generator, '_load_existing_examples', return_value=existing_examples), \
             patch.object(generator, 'generate_examples_with_llm', return_value=new_examples), \
             patch('example_generator.Path') as mock_path:
            
            mock_path.return_value.parent.parent = temp_test_queries_file.parent
            
            result = await generator.merge_and_save_examples()
            
            # Should have 2 examples (existing + new, duplicate should be filtered out)
            assert len(result) == 2
            assert result[0]["name"] == "Existing Query"
            assert result[1]["name"] == "New Query"

    @pytest.mark.asyncio
    async def test_merge_and_save_examples_error(self, generator):
        """Test merging and saving with error"""
        with patch.object(generator, '_load_existing_examples', side_effect=Exception("Load error")):
            result = await generator.merge_and_save_examples()
            
            assert result == []
