import os
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://localhost/phantom"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # OpenAI API
    openai_api_key: str = ""
    
    # JWT Secret
    jwt_secret: str = "your-secret-key-here"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # Security API Keys
    shodan_api_key: str = ""
    
    # Scanning limits
    max_concurrent_scans: int = 5
    scan_timeout_minutes: int = 30
    
    # CORS
    backend_cors_origins: list[str] = ["http://localhost:3000"]
    
    # Environment
    environment: str = "development"
    
    # Email Settings (Optional)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    
    # Webhook Settings (Optional)
    slack_webhook_url: str = ""
    discord_webhook_url: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

settings = Settings()