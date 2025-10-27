from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.core.database.connection_manager import DatabaseConnectionManager, ConnectionPoolConfig

# Enhanced database connection manager
db_config = ConnectionPoolConfig(
    pool_size=getattr(settings, 'db_pool_size', 10),
    max_overflow=getattr(settings, 'db_max_overflow', 20),
    pool_timeout=getattr(settings, 'db_pool_timeout', 30),
    pool_recycle=getattr(settings, 'db_pool_recycle', 3600),
    pool_pre_ping=getattr(settings, 'db_pool_pre_ping', True),
    enable_monitoring=getattr(settings, 'db_enable_monitoring', True)
)

# Initialize connection manager
connection_manager = DatabaseConnectionManager(settings.database_url, db_config)

# Legacy support - keep existing interface
engine = connection_manager.engine
SessionLocal = connection_manager.session_factory

Base = declarative_base()

def get_db():
    """Get database session - enhanced with connection pooling"""
    with connection_manager.get_session() as session:
        yield session

# Additional utilities
def get_db_metrics():
    """Get database connection metrics"""
    return connection_manager.get_metrics()

def get_db_health():
    """Get database health status"""
    import asyncio
    return asyncio.run(connection_manager.health_check())