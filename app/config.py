"""Настройки API приложения (отдельная БД app_bot_db)."""
from typing import Optional

from pydantic import AliasChoices, Field, SecretStr
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
    app_allow_unpaid_test_contact: bool = False
    app_allow_guest_auth: bool = False
    app_email_smtp_host: str = ""
    app_email_smtp_port: int = 465
    app_email_smtp_user: str = ""
    app_email_smtp_password: Optional[SecretStr] = None
    app_email_from: str = ""
    app_email_smtp_ssl: bool = True
    app_tarologist_profile_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "app_tarologist_profile_url",
            "APP_TAROLOGIST_PROFILE_URL",
            "TAROLOGIST_PROFILE_URL",
        ),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


app_config = AppSettings()
