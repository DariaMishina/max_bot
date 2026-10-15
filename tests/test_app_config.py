import os
import unittest

for key, value in {
    "APP_DB_USER": "test", "APP_DB_PASSWORD": "test", "APP_JWT_SECRET": "test-only",
}.items():
    os.environ.setdefault(key, value)

from app.config import AppSettings


class AppEnvironmentConfigTests(unittest.TestCase):
    def base_production(self) -> dict:
        return {
            "app_environment": "production",
            "app_api_public_url": "https://api.example.com/",
            "app_db_name": "app_bot_prod_db",
            "app_db_user": "app_bot_prod_user",
            "app_db_password": "production-db-password",
            "app_jwt_secret": "production-jwt-secret-with-32-characters",
            "app_allow_guest_auth": False,
            "app_allow_unpaid_test_contact": False,
            "app_rustore_sandbox": False,
            "app_rustore_console_app_id": 123,
            "app_rustore_key_id": "key-id",
            "app_rustore_private_key": "private-key",
            "app_rustore_callback_key": "callback-key",
            "app_email_smtp_password": "smtp-password",
            "app_email_smtp_host": "smtp.example.com",
            "app_email_smtp_user": "sender@example.com",
            "app_email_from": "sender@example.com",
        }

    def test_staging_keeps_test_features_available(self):
        settings = AppSettings(
            _env_file=None,
            app_environment="staging",
            app_db_user="app_bot_user",
            app_db_password="short",
            app_jwt_secret="short",
            app_allow_guest_auth=True,
            app_rustore_sandbox=True,
        )
        self.assertEqual(settings.app_environment, "staging")

    def test_production_accepts_isolated_safe_configuration(self):
        settings = AppSettings(_env_file=None, **self.base_production())
        self.assertEqual(settings.app_db_name, "app_bot_prod_db")
        self.assertFalse(settings.app_rustore_sandbox)

    def test_production_rejects_staging_database_and_test_flags(self):
        values = self.base_production()
        values.update({
            "app_db_name": "app_bot_db",
            "app_db_user": "app_bot_user",
            "app_allow_guest_auth": True,
            "app_allow_unpaid_test_contact": True,
            "app_rustore_sandbox": True,
        })
        with self.assertRaisesRegex(ValueError, "Invalid production configuration"):
            AppSettings(_env_file=None, **values)

    def test_production_rejects_missing_secrets_and_http_url(self):
        values = self.base_production()
        values.update({
            "app_api_public_url": "http://localhost:8083",
            "app_rustore_private_key": None,
            "app_rustore_callback_key": None,
            "app_email_smtp_password": None,
        })
        with self.assertRaisesRegex(ValueError, "Invalid production configuration"):
            AppSettings(_env_file=None, **values)


if __name__ == "__main__":
    unittest.main()
