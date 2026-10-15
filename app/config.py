"""Настройки API приложения с жёстким разделением staging/production."""
import os
from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    app_environment: Literal["staging", "production"] = "staging"
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
    app_vk_client_id: str = "54803401"
    app_rustore_console_app_id: int = 0
    app_rustore_key_id: str = ""
    app_rustore_private_key: Optional[SecretStr] = None
    app_rustore_callback_key: Optional[SecretStr] = None
    app_rustore_api_base_url: str = "https://public-api-m.rustore.ru"
    app_rustore_sandbox: bool = True
    app_tarologist_profile_url: str = Field(
        default="",
        validation_alias=AliasChoices(
            "app_tarologist_profile_url",
            "APP_TAROLOGIST_PROFILE_URL",
            "TAROLOGIST_PROFILE_URL",
        ),
    )

    @model_validator(mode="after")
    def validate_environment_isolation(self) -> "AppSettings":
        if self.app_environment != "production":
            return self

        errors: list[str] = []
        parsed_url = urlparse(self.app_api_public_url)
        if (
            parsed_url.scheme != "https"
            or not parsed_url.hostname
            or parsed_url.hostname in {"localhost", "127.0.0.1"}
        ):
            errors.append("APP_API_PUBLIC_URL must be a public HTTPS URL")
        if self.app_allow_guest_auth:
            errors.append("APP_ALLOW_GUEST_AUTH must be false")
        if self.app_allow_unpaid_test_contact:
            errors.append("APP_ALLOW_UNPAID_TEST_CONTACT must be false")
        if self.app_rustore_sandbox:
            errors.append("APP_RUSTORE_SANDBOX must be false")
        if self.app_db_name == "app_bot_db" or any(
            marker in self.app_db_name.lower() for marker in ("staging", "test")
        ):
            errors.append("APP_DB_NAME must identify a separate production database")
        if self.app_db_user.get_secret_value() == "app_bot_user":
            errors.append("APP_DB_USER must be a separate production role")
        if len(self.app_db_password.get_secret_value()) < 16:
            errors.append("APP_DB_PASSWORD must contain at least 16 characters")
        if len(self.app_jwt_secret.get_secret_value()) < 32:
            errors.append("APP_JWT_SECRET must contain at least 32 characters")
        required_secrets = {
            "APP_RUSTORE_PRIVATE_KEY": self.app_rustore_private_key,
            "APP_RUSTORE_CALLBACK_KEY": self.app_rustore_callback_key,
            "APP_EMAIL_SMTP_PASSWORD": self.app_email_smtp_password,
        }
        for name, value in required_secrets.items():
            if value is None or not value.get_secret_value().strip():
                errors.append(f"{name} must be configured")
        if not self.app_rustore_key_id.strip():
            errors.append("APP_RUSTORE_KEY_ID must be configured")
        if self.app_rustore_console_app_id <= 0:
            errors.append("APP_RUSTORE_CONSOLE_APP_ID must be configured")
        if not self.app_email_smtp_host.strip() or not self.app_email_smtp_user.strip() or not self.app_email_from.strip():
            errors.append("production email sender must be configured")

        if errors:
            raise ValueError("Invalid production configuration: " + "; ".join(errors))
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


app_config = AppSettings(_env_file=os.getenv("APP_CONFIG_FILE", ".env"))
