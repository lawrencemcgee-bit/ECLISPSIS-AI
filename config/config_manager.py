from pathlib import Path
from typing import Optional

from pydantic import BaseSettings
from dotenv import load_dotenv


class AppSettings(BaseSettings):
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class ConfigManager:
    _settings: Optional[AppSettings] = None

    @classmethod
    def load(cls) -> AppSettings:
        if cls._settings is None:
            load_dotenv()
            cls._settings = AppSettings()
        return cls._settings

    @classmethod
    def get(cls) -> AppSettings:
        if cls._settings is None:
            return cls.load()
        return cls._settings
