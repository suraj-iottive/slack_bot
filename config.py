import os
# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Server Config
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # Slack Config
    SLACK_BOT_TOKEN: str = ""
    SLACK_SIGNING_SECRET: str = ""
    DEFAULT_SLACK_CHANNEL: str = "#releases"

    # Bitrise Config
    BITRISE_TOKEN: str = ""
    BITRISE_APP_SLUG: str = ""

    # Linear & Slack Canvas Config
    LINEAR_API_KEY: str = ""
    SLACK_CANVAS_ID: str = ""

    # Workflow Config
    ANDROID_WORKFLOW: str = "deploy-android"
    IOS_WORKFLOW: str = "deploy"
    BOTH_WORKFLOW: str = ""

    # Pydantic settings config to load from .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate settings
settings = Settings()
