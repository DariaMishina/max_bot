"""Настройки API приложения (отдельная БД app_bot_db)."""
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    app_db_host: str = "localhost"
    app_db_port: int = 5432
    app_db_name: str = "app_bot_db"
    app_db_user: SecretStr
    app_db_password: SecretStr
    app_api_port: int = 8083
    app_jwt_secret: SecretStr
    app_api_public_url: str = ""
    app_tarologist_profile_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


app_config = AppSettings()
