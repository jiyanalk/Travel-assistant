from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    app_name: str = Field(default="travel-planning-agent", alias="APP_NAME")
    app_version: str = "0.1.0"

    zai_api_key: str | None = Field(default=None, alias="ZAI_API_KEY")
    zhipu_model: str = Field(default="glm-5.1", alias="ZHIPU_MODEL")
    zhipu_base_url: str = Field(
        default="https://open.bigmodel.cn/api/paas/v4/",
        alias="ZHIPU_BASE_URL",
    )

    database_url: str = Field(
        default=f"sqlite:///{(ROOT_DIR / 'travel_agent.db').as_posix()}",
        alias="DATABASE_URL",
    )
    vector_store_path: str = Field(
        default=str(ROOT_DIR / "data" / "vector_store"),
        alias="VECTOR_STORE_PATH",
    )
    default_currency: str = "CNY"

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
