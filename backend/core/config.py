from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    PROJECT_NAME: str = "ROOTED AI"
    SUPABASE_URL: str
    SUPABASE_KEY: str
    OPENAI_API_KEY: str
    CHROMA_DB_PATH: str = "./chroma_db"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000,http://localhost:5173,https://rooted-ai.vercel.app,https://rooted-ai-tau.vercel.app"
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
