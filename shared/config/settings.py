"""
Centralized configuration management using Pydantic Settings.
Loads configuration from environment variables with validation.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Global application settings"""
    
    # OpenAI Configuration
    openai_api_key: str
    openai_model: str = "gpt-4-turbo-preview"
    
    # Pinecone Configuration
    pinecone_api_key: str
    pinecone_environment: str
    pinecone_index_name: str = "news-curator"
    
    # Kafka Configuration
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_topic_raw_news: str = "raw-news"
    kafka_topic_structured_graph: str = "structured-graph-event"
    kafka_topic_user_feed: str = "user-feed-event"
    
    # Neo4j Configuration
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str
    
    # PostgreSQL Configuration
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "news_curator"
    postgres_user: str = "curator"
    postgres_password: str
    
    # Redis Configuration
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: Optional[str] = None
    redis_db: int = 0
    
    # Celery Configuration
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"
    
    # API Gateway
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # External APIs
    crunchbase_api_key: Optional[str] = None
    wikidata_api_endpoint: str = "https://www.wikidata.org/w/api.php"
    
    # Monitoring
    log_level: str = "INFO"
    sentry_dsn: Optional[str] = None
    
    # Service Configuration
    ingestion_poll_interval_minutes: int = 15
    duplicate_detection_ttl_days: int = 7
    feed_cache_ttl_hours: int = 24
    max_graph_depth: int = 3
    
    @property
    def postgres_url(self) -> str:
        """Construct PostgreSQL connection URL"""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    @property
    def redis_url(self) -> str:
        """Construct Redis connection URL"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
