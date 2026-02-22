import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, field_validator


class Settings(BaseSettings):
    # Режим работы: test или production
    test_mode: bool = False
    # Суффикс для таблиц БД
    db_table_suffix: str = ""
    
    # Токен бота Max (получить у @MasterBot)
    bot_token: Optional[SecretStr] = None
    bot_token_test: Optional[SecretStr] = None
    
    # OpenAI API Key
    api_key: SecretStr
    # Для внешней ссылки на оплату через ЮKassa API
    yookassa_shop_id: Optional[SecretStr] = None
    yookassa_secret_key: Optional[SecretStr] = None
    # PostgreSQL настройки
    db_host: str  
    db_port: int  
    db_name: str  
    db_user: SecretStr  
    db_password: SecretStr  
    # Яндекс Метрика Measurement Protocol
    metrika_mp_counter_id: Optional[int] = None
    metrika_mp_token: Optional[str] = None
    # URL вебхук-сервера (для мини-приложений и платежей)
    service_url: Optional[str] = None
    # Куда пересылать обратную связь (Max user_id админа)
    admin_chat_id: Optional[int] = None
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    @field_validator("metrika_mp_counter_id", "admin_chat_id", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v
    
    def __init__(self, **kwargs):
        if 'test_mode' not in kwargs:
            test_mode_str = os.environ.get('TEST_MODE', 'false')
            kwargs['test_mode'] = test_mode_str.lower() in ('true', '1', 'yes', 'on')
        
        if 'db_table_suffix' not in kwargs or not kwargs.get('db_table_suffix'):
            db_suffix = os.environ.get('DB_TABLE_SUFFIX', '')
            if db_suffix:
                kwargs['db_table_suffix'] = db_suffix
            else:
                test_mode = kwargs.get('test_mode', False)
                if isinstance(test_mode, str):
                    test_mode = test_mode.lower() in ('true', '1', 'yes', 'on')
                kwargs['db_table_suffix'] = "_test" if test_mode else ""
        
        super().__init__(**kwargs)
        
        if self.test_mode and self.bot_token_test:
            self._effective_bot_token = self.bot_token_test
        elif self.bot_token:
            self._effective_bot_token = self.bot_token
        else:
            raise ValueError(
                "BOT_TOKEN is required. "
                "For test mode, set BOT_TOKEN_TEST or BOT_TOKEN in environment variables."
            )
    
    @property
    def effective_bot_token(self) -> SecretStr:
        """Возвращает токен бота в зависимости от режима"""
        return self._effective_bot_token


config = Settings()
