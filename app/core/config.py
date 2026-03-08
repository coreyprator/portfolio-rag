"""Portfolio RAG Configuration"""

import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    VERSION: str = "2.3.0"
    BUILD: str = os.getenv("COMMIT_SHA", os.getenv("BUILD_ID", "unknown"))

    GITHUB_TOKEN: str = ""
    WEBHOOK_SECRET: str = ""
    RAG_API_KEY: str = ""
    OAUTH_CLIENT_ID: str = ""
    OPENAI_API_KEY: str = ""
    REINGEST_TOKEN: str = ""
    REPO_OWNER: str = "coreyprator"
    REPOS: List[str] = [
        "project-methodology",
        "metapm",
        "ArtForge",
        "harmonylab",
        "Super-Flashcards",
        "etymython",
    ]

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: List[str] = ["*", "null"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
