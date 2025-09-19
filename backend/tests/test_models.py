"""
Comprehensive pytest tests for Pydantic models
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from models import (
    PriorityLevel, QueryAnalysisRequest, ExecutionPlan, ResourceMetrics,
    OptimizationRecommendation, QueryAnalysis, DatabaseConfig, HealthCheck,
    LLMResourceMetrics, LLMOptimizationRecommendation, LLMAnalysisResponse,
    ExecutionPlanResponse
)


class TestPriorityLevel:
    """Test cases for PriorityLevel enum"""

    def test_priority_level_values(self):
        """Test PriorityLevel enum values"""
        assert PriorityLevel.HIGH == "high"
        assert PriorityLevel.MEDIUM == "medium"
        assert PriorityLevel.LOW == "low"

    def test_priority_level_validation(self):
        """Test PriorityLevel validation"""
        # Valid values
        assert PriorityLevel("high") == PriorityLevel.HIGH
        assert PriorityLevel("medium") == PriorityLevel.MEDIUM
        assert PriorityLevel("low") == PriorityLevel.LOW

        # Invalid value should raise ValueError
        with pytest.raises(ValueError):
            PriorityLevel("invalid")


class TestQueryAnalysisRequest:
    """Test cases for QueryAnalysisRequest model"""

    def test_query_analysis_request_creation(self):
        """Test QueryAnalysisRequest creation with required fields"""
        request = QueryAnalysisRequest(query="SELECT * FROM users WHERE id = 1")
        
        assert request.query == "SELECT * FROM users WHERE id = 1"
        assert request.database_url is None
        assert request.database_profile_id is None

    def test_query_analysis_request_with_optional_fields(self):
        """Test QueryAnalysisRequest creation with optional fields"""
        request = QueryAnalysisRequest(
            query="SELECT * FROM users WHERE id = 1",
            database_url="postgresql://user:pass@localhost:5432/db",
            database_profile_id="profile123"
        )
        
        assert request.query == "SELECT * FROM users WHERE id = 1"
        assert request.database_url == "postgresql://user:pass@localhost:5432/db"
        assert request.database_profile_id == "profile123"

    def test_query_analysis_request_validation_error(self):
        """Test QueryAnalysisRequest validation error"""
        with pytest.raises(ValidationError):
            QueryAnalysisRequest()  # Missing required field


class TestExecutionPlan:
    """Test cases for ExecutionPlan model"""

    def test_execution_plan_creation(self):
        """Test ExecutionPlan creation"""
        plan = ExecutionPlan(
            total_cost=100.0,
            execution_time=50.0,
            rows=1000,
            width=64,
            plan_json={"Node Type": "Seq Scan", "Total Cost": 100.0}
        )
        
        assert plan.total_cost == 100.0
        assert plan.execution_time == 50.0
        assert plan.rows == 1000
        assert plan.width == 64
        assert plan.plan_json == {"Node Type": "Seq Scan", "Total Cost": 100.0}

    def test_execution_plan_validation_error(self):
        """Test ExecutionPlan validation error"""
        with pytest.raises(ValidationError):
            ExecutionPlan(
                total_cost=100.0,
                execution_time=50.0,
                rows=1000,
                width=64
                # Missing plan_json
            )


class TestResourceMetrics:
    """Test cases for ResourceMetrics model"""

    def test_resource_metrics_creation_required_fields(self):
        """Test ResourceMetrics creation with required fields"""
        metrics = ResourceMetrics(
            cpu_usage=75.0,
            memory_usage=128.0,
            io_operations=10,
            disk_reads=5,
            disk_writes=2
        )
        
        assert metrics.cpu_usage == 75.0
        assert metrics.memory_usage == 128.0
        assert metrics.io_operations == 10
        assert metrics.disk_reads == 5
        assert metrics.disk_writes == 2
        assert metrics.disk_io is None
        assert metrics.network_io is None

    def test_resource_metrics_creation_all_fields(self):
        """Test ResourceMetrics creation with all fields"""
        metrics = ResourceMetrics(
            cpu_usage=75.0,
            memory_usage=128.0,
            io_operations=10,
            disk_reads=5,
            disk_writes=2,
            disk_io=7.0,
            network_io=1.5,
            execution_time=50.0,
            rows_processed=1000,
            index_usage=80.0,
            cache_hit_ratio=95.0,
            lock_contention=5.0
        )
        
        assert metrics.cpu_usage == 75.0
        assert metrics.memory_usage == 128.0
        assert metrics.io_operations == 10
        assert metrics.disk_reads == 5
        assert metrics.disk_writes == 2
        assert metrics.disk_io == 7.0
        assert metrics.network_io == 1.5
        assert metrics.execution_time == 50.0
        assert metrics.rows_processed == 1000
        assert metrics.index_usage == 80.0
        assert metrics.cache_hit_ratio == 95.0
        assert metrics.lock_contention == 5.0

    def test_resource_metrics_validation_error(self):
        """Test ResourceMetrics validation error"""
        with pytest.raises(ValidationError):
            ResourceMetrics(
                cpu_usage=75.0,
                memory_usage=128.0,
                io_operations=10,
                disk_reads=5
                # Missing disk_writes
            )


class TestOptimizationRecommendation:
    """Test cases for OptimizationRecommendation model"""

    def test_optimization_recommendation_creation(self):
        """Test OptimizationRecommendation creation"""
        recommendation = OptimizationRecommendation(
            type="index",
            priority=PriorityLevel.HIGH,
            title="Add index on email column",
            description="Create an index on the email column to improve query performance",
            potential_improvement="Will reduce query execution time by 50-70%",
            implementation="CREATE INDEX idx_users_email ON users(email);",
            estimated_speedup=60.0
        )
        
        assert recommendation.type == "index"
        assert recommendation.priority == PriorityLevel.HIGH
        assert recommendation.title == "Add index on email column"
        assert recommendation.description == "Create an index on the email column to improve query performance"
        assert recommendation.potential_improvement == "Will reduce query execution time by 50-70%"
        assert recommendation.implementation == "CREATE INDEX idx_users_email ON users(email);"
        assert recommendation.estimated_speedup == 60.0

    def test_optimization_recommendation_without_speedup(self):
        """Test OptimizationRecommendation creation without estimated_speedup"""
        recommendation = OptimizationRecommendation(
            type="index",
            priority=PriorityLevel.MEDIUM,
            title="Add index on email column",
            description="Create an index on the email column to improve query performance",
            potential_improvement="Will reduce query execution time by 50-70%",
            implementation="CREATE INDEX idx_users_email ON users(email);"
        )
        
        assert recommendation.estimated_speedup is None

    def test_optimization_recommendation_validation_error(self):
        """Test OptimizationRecommendation validation error"""
        with pytest.raises(ValidationError):
            OptimizationRecommendation(
                type="index",
                priority=PriorityLevel.HIGH,
                title="Add index on email column"
                # Missing required fields
            )


class TestQueryAnalysis:
    """Test cases for QueryAnalysis model"""

    def test_query_analysis_creation(self):
        """Test QueryAnalysis creation"""
        execution_plan = ExecutionPlan(
            total_cost=100.0,
            execution_time=50.0,
            rows=1000,
            width=64,
            plan_json={"Node Type": "Seq Scan", "Total Cost": 100.0}
        )
        
        resource_metrics = ResourceMetrics(
            cpu_usage=75.0,
            memory_usage=128.0,
            io_operations=10,
            disk_reads=5,
            disk_writes=2
        )
        
        recommendation = OptimizationRecommendation(
            type="index",
            priority=PriorityLevel.HIGH,
            title="Add index on email column",
            description="Create an index on the email column to improve query performance",
            potential_improvement="Will reduce query execution time by 50-70%",
            implementation="CREATE INDEX idx_users_email ON users(email);",
            estimated_speedup=60.0
        )
        
        analysis = QueryAnalysis(
            query="SELECT * FROM users WHERE email = 'test@example.com'",
            rewritten_query="SELECT id, name FROM users WHERE email = 'test@example.com'",
            execution_plan=execution_plan,
            resource_metrics=resource_metrics,
            recommendations=[recommendation],
            warnings=["High CPU usage detected"]
        )
        
        assert analysis.query == "SELECT * FROM users WHERE email = 'test@example.com'"
        assert analysis.rewritten_query == "SELECT id, name FROM users WHERE email = 'test@example.com'"
        assert analysis.execution_plan == execution_plan
        assert analysis.resource_metrics == resource_metrics
        assert len(analysis.recommendations) == 1
        assert analysis.recommendations[0] == recommendation
        assert analysis.warnings == ["High CPU usage detected"]
        assert analysis.has_errors is False
        assert analysis.postgresql_errors == []
        assert analysis.error_analysis is None

    def test_query_analysis_with_errors(self):
        """Test QueryAnalysis creation with errors"""
        execution_plan = ExecutionPlan(
            total_cost=0.0,
            execution_time=0.0,
            rows=0,
            width=0,
            plan_json={"Node Type": "Error", "Error": "Table does not exist"}
        )
        
        resource_metrics = ResourceMetrics(
            cpu_usage=0.0,
            memory_usage=0.0,
            io_operations=0,
            disk_reads=0,
            disk_writes=0
        )
        
        analysis = QueryAnalysis(
            query="SELECT * FROM nonexistent_table",
            execution_plan=execution_plan,
            resource_metrics=resource_metrics,
            recommendations=[],
            warnings=[],
            has_errors=True,
            postgresql_errors=["relation \"nonexistent_table\" does not exist"],
            error_analysis="Table 'nonexistent_table' does not exist in the database"
        )
        
        assert analysis.has_errors is True
        assert analysis.postgresql_errors == ["relation \"nonexistent_table\" does not exist"]
        assert analysis.error_analysis == "Table 'nonexistent_table' does not exist in the database"

    def test_query_analysis_default_values(self):
        """Test QueryAnalysis creation with default values"""
        execution_plan = ExecutionPlan(
            total_cost=100.0,
            execution_time=50.0,
            rows=1000,
            width=64,
            plan_json={"Node Type": "Seq Scan", "Total Cost": 100.0}
        )
        
        resource_metrics = ResourceMetrics(
            cpu_usage=75.0,
            memory_usage=128.0,
            io_operations=10,
            disk_reads=5,
            disk_writes=2
        )
        
        analysis = QueryAnalysis(
            query="SELECT * FROM users",
            execution_plan=execution_plan,
            resource_metrics=resource_metrics,
            recommendations=[]
        )
        
        assert analysis.rewritten_query is None
        assert analysis.warnings == []
        assert analysis.has_errors is False
        assert analysis.postgresql_errors == []
        assert analysis.error_analysis is None
        assert isinstance(analysis.analysis_timestamp, datetime)


class TestDatabaseConfig:
    """Test cases for DatabaseConfig model"""

    def test_database_config_creation(self):
        """Test DatabaseConfig creation"""
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="testdb",
            username="testuser",
            password="testpass"
        )
        
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "testdb"
        assert config.username == "testuser"
        assert config.password == "testpass"

    def test_database_config_default_port(self):
        """Test DatabaseConfig creation with default port"""
        config = DatabaseConfig(
            host="localhost",
            database="testdb",
            username="testuser",
            password="testpass"
        )
        
        assert config.port == 5432  # Default value

    def test_database_config_validation_error(self):
        """Test DatabaseConfig validation error"""
        with pytest.raises(ValidationError):
            DatabaseConfig(
                host="localhost",
                port=5432,
                database="testdb"
                # Missing username and password
            )


class TestHealthCheck:
    """Test cases for HealthCheck model"""

    def test_health_check_creation(self):
        """Test HealthCheck creation"""
        timestamp = datetime.now()
        health = HealthCheck(
            status="healthy",
            timestamp=timestamp,
            database_connected=True,
            openai_available=True
        )
        
        assert health.status == "healthy"
        assert health.timestamp == timestamp
        assert health.database_connected is True
        assert health.openai_available is True

    def test_health_check_unhealthy(self):
        """Test HealthCheck creation for unhealthy status"""
        timestamp = datetime.now()
        health = HealthCheck(
            status="unhealthy",
            timestamp=timestamp,
            database_connected=False,
            openai_available=False
        )
        
        assert health.status == "unhealthy"
        assert health.database_connected is False
        assert health.openai_available is False

    def test_health_check_validation_error(self):
        """Test HealthCheck validation error"""
        with pytest.raises(ValidationError):
            HealthCheck(
                status="healthy",
                timestamp=datetime.now()
                # Missing database_connected and openai_available
            )


class TestLLMResourceMetrics:
    """Test cases for LLMResourceMetrics model"""

    def test_llm_resource_metrics_creation(self):
        """Test LLMResourceMetrics creation"""
        metrics = LLMResourceMetrics(
            cpu_usage=75.0,
            memory_usage=128.0,
            io_operations=10,
            disk_reads=5,
            disk_writes=2,
            disk_io=7.0,
            network_io=1.5,
            execution_time=50.0,
            rows_processed=1000,
            index_usage=80.0,
            cache_hit_ratio=95.0,
            lock_contention=5.0
        )
        
        assert metrics.cpu_usage == 75.0
        assert metrics.memory_usage == 128.0
        assert metrics.io_operations == 10
        assert metrics.disk_reads == 5
        assert metrics.disk_writes == 2
        assert metrics.disk_io == 7.0
        assert metrics.network_io == 1.5
        assert metrics.execution_time == 50.0
        assert metrics.rows_processed == 1000
        assert metrics.index_usage == 80.0
        assert metrics.cache_hit_ratio == 95.0
        assert metrics.lock_contention == 5.0

    def test_llm_resource_metrics_with_none_values(self):
        """Test LLMResourceMetrics creation with None values for optional fields"""
        metrics = LLMResourceMetrics(
            cpu_usage=75.0,
            memory_usage=128.0,
            io_operations=10,
            disk_reads=5,
            disk_writes=2,
            disk_io=None,
            network_io=None,
            execution_time=None,
            rows_processed=None,
            index_usage=None,
            cache_hit_ratio=None,
            lock_contention=None
        )
        
        assert metrics.disk_io is None
        assert metrics.network_io is None
        assert metrics.execution_time is None
        assert metrics.rows_processed is None
        assert metrics.index_usage is None
        assert metrics.cache_hit_ratio is None
        assert metrics.lock_contention is None


class TestLLMOptimizationRecommendation:
    """Test cases for LLMOptimizationRecommendation model"""

    def test_llm_optimization_recommendation_creation(self):
        """Test LLMOptimizationRecommendation creation"""
        recommendation = LLMOptimizationRecommendation(
            type="index",
            priority="high",
            title="Add index on email column",
            description="Create an index on the email column to improve query performance",
            potential_improvement="Will reduce query execution time by 50-70%",
            implementation="CREATE INDEX idx_users_email ON users(email);",
            estimated_speedup=60.0
        )
        
        assert recommendation.type == "index"
        assert recommendation.priority == "high"
        assert recommendation.title == "Add index on email column"
        assert recommendation.description == "Create an index on the email column to improve query performance"
        assert recommendation.potential_improvement == "Will reduce query execution time by 50-70%"
        assert recommendation.implementation == "CREATE INDEX idx_users_email ON users(email);"
        assert recommendation.estimated_speedup == 60.0

    def test_llm_optimization_recommendation_without_speedup(self):
        """Test LLMOptimizationRecommendation creation without estimated_speedup"""
        recommendation = LLMOptimizationRecommendation(
            type="index",
            priority="medium",
            title="Add index on email column",
            description="Create an index on the email column to improve query performance",
            potential_improvement="Will reduce query execution time by 50-70%",
            implementation="CREATE INDEX idx_users_email ON users(email);"
        )
        
        assert recommendation.estimated_speedup is None


class TestLLMAnalysisResponse:
    """Test cases for LLMAnalysisResponse model"""

    def test_llm_analysis_response_creation(self):
        """Test LLMAnalysisResponse creation"""
        resource_metrics = LLMResourceMetrics(
            cpu_usage=75.0,
            memory_usage=128.0,
            io_operations=10,
            disk_reads=5,
            disk_writes=2
        )
        
        recommendation = LLMOptimizationRecommendation(
            type="index",
            priority="high",
            title="Add index on email column",
            description="Create an index on the email column to improve query performance",
            potential_improvement="Will reduce query execution time by 50-70%",
            implementation="CREATE INDEX idx_users_email ON users(email);",
            estimated_speedup=60.0
        )
        
        response = LLMAnalysisResponse(
            rewritten_query="SELECT id, name FROM users WHERE email = 'test@example.com'",
            resource_metrics=resource_metrics,
            recommendations=[recommendation],
            warnings=["High CPU usage detected"]
        )
        
        assert response.rewritten_query == "SELECT id, name FROM users WHERE email = 'test@example.com'"
        assert response.resource_metrics == resource_metrics
        assert len(response.recommendations) == 1
        assert response.recommendations[0] == recommendation
        assert response.warnings == ["High CPU usage detected"]

    def test_llm_analysis_response_without_rewritten_query(self):
        """Test LLMAnalysisResponse creation without rewritten_query"""
        resource_metrics = LLMResourceMetrics(
            cpu_usage=75.0,
            memory_usage=128.0,
            io_operations=10,
            disk_reads=5,
            disk_writes=2
        )
        
        response = LLMAnalysisResponse(
            resource_metrics=resource_metrics,
            recommendations=[],
            warnings=[]
        )
        
        assert response.rewritten_query is None
        assert response.resource_metrics == resource_metrics
        assert response.recommendations == []
        assert response.warnings == []


class TestExecutionPlanResponse:
    """Test cases for ExecutionPlanResponse model"""

    def test_execution_plan_response_creation(self):
        """Test ExecutionPlanResponse creation"""
        execution_plan = ExecutionPlan(
            total_cost=100.0,
            execution_time=50.0,
            rows=1000,
            width=64,
            plan_json={"Node Type": "Seq Scan", "Total Cost": 100.0}
        )
        
        response = ExecutionPlanResponse(
            query="SELECT * FROM users WHERE id = 1",
            execution_plan=execution_plan,
            status="execution_plan_ready",
            has_errors=False,
            postgresql_errors=[],
            error_analysis=None
        )
        
        assert response.query == "SELECT * FROM users WHERE id = 1"
        assert response.execution_plan == execution_plan
        assert response.status == "execution_plan_ready"
        assert response.has_errors is False
        assert response.postgresql_errors == []
        assert response.error_analysis is None
        assert isinstance(response.analysis_timestamp, datetime)

    def test_execution_plan_response_with_errors(self):
        """Test ExecutionPlanResponse creation with errors"""
        execution_plan = ExecutionPlan(
            total_cost=0.0,
            execution_time=0.0,
            rows=0,
            width=0,
            plan_json={"Node Type": "Error", "Error": "Table does not exist"}
        )
        
        response = ExecutionPlanResponse(
            query="SELECT * FROM nonexistent_table",
            execution_plan=execution_plan,
            status="execution_plan_error",
            has_errors=True,
            postgresql_errors=["relation \"nonexistent_table\" does not exist"],
            error_analysis="Table 'nonexistent_table' does not exist in the database"
        )
        
        assert response.has_errors is True
        assert response.postgresql_errors == ["relation \"nonexistent_table\" does not exist"]
        assert response.error_analysis == "Table 'nonexistent_table' does not exist in the database"

    def test_execution_plan_response_default_values(self):
        """Test ExecutionPlanResponse creation with default values"""
        execution_plan = ExecutionPlan(
            total_cost=100.0,
            execution_time=50.0,
            rows=1000,
            width=64,
            plan_json={"Node Type": "Seq Scan", "Total Cost": 100.0}
        )
        
        response = ExecutionPlanResponse(
            query="SELECT * FROM users",
            execution_plan=execution_plan,
            status="execution_plan_ready"
        )
        
        assert response.has_errors is False
        assert response.postgresql_errors == []
        assert response.error_analysis is None
        assert isinstance(response.analysis_timestamp, datetime)


class TestModelValidation:
    """Test cases for model validation edge cases"""

    def test_priority_level_string_validation(self):
        """Test PriorityLevel validation with string values"""
        # Should work with string values
        assert PriorityLevel("high") == PriorityLevel.HIGH
        assert PriorityLevel("medium") == PriorityLevel.MEDIUM
        assert PriorityLevel("low") == PriorityLevel.LOW

    def test_resource_metrics_type_validation(self):
        """Test ResourceMetrics type validation"""
        # Should accept float values
        metrics = ResourceMetrics(
            cpu_usage=75.5,
            memory_usage=128.7,
            io_operations=10,
            disk_reads=5,
            disk_writes=2
        )
        
        assert metrics.cpu_usage == 75.5
        assert metrics.memory_usage == 128.7

    def test_optimization_recommendation_priority_validation(self):
        """Test OptimizationRecommendation priority validation"""
        # Should accept PriorityLevel enum
        recommendation = OptimizationRecommendation(
            type="index",
            priority=PriorityLevel.HIGH,
            title="Test",
            description="Test description",
            potential_improvement="Test improvement",
            implementation="Test implementation"
        )
        
        assert recommendation.priority == PriorityLevel.HIGH

    def test_query_analysis_timestamp_auto_generation(self):
        """Test QueryAnalysis timestamp auto-generation"""
        execution_plan = ExecutionPlan(
            total_cost=100.0,
            execution_time=50.0,
            rows=1000,
            width=64,
            plan_json={"Node Type": "Seq Scan", "Total Cost": 100.0}
        )
        
        resource_metrics = ResourceMetrics(
            cpu_usage=75.0,
            memory_usage=128.0,
            io_operations=10,
            disk_reads=5,
            disk_writes=2
        )
        
        analysis = QueryAnalysis(
            query="SELECT * FROM users",
            execution_plan=execution_plan,
            resource_metrics=resource_metrics,
            recommendations=[]
        )
        
        # Timestamp should be automatically generated
        assert isinstance(analysis.analysis_timestamp, datetime)
        assert analysis.analysis_timestamp <= datetime.now()

    def test_model_serialization(self):
        """Test model serialization to dict"""
        request = QueryAnalysisRequest(
            query="SELECT * FROM users WHERE id = 1",
            database_url="postgresql://user:pass@localhost:5432/db"
        )
        
        request_dict = request.model_dump()
        
        assert request_dict["query"] == "SELECT * FROM users WHERE id = 1"
        assert request_dict["database_url"] == "postgresql://user:pass@localhost:5432/db"
        assert request_dict["database_profile_id"] is None

    def test_model_json_serialization(self):
        """Test model JSON serialization"""
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            database="testdb",
            username="testuser",
            password="testpass"
        )
        
        config_json = config.model_dump_json()
        
        assert '"host":"localhost"' in config_json
        assert '"port":5432' in config_json
        assert '"database":"testdb"' in config_json
        assert '"username":"testuser"' in config_json
        assert '"password":"testpass"' in config_json
