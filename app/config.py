from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # 数据库
    database_url: str
    redis_url: str

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # LLM
    llm_api_key: str
    llm_api_url: str
    llm_model: str = "glm-4-flash"

    # 文件上传
    upload_dir: str = "./uploads"
    max_file_size: int = 52428800

    # Embedding 模型
    embedding_model: str = "BAAI/bge-m3"

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()