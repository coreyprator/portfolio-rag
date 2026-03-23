"""Portfolio RAG Configuration"""

import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    VERSION: str = "2.8.0"
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

    # SQL Server (Cloud SQL) — word_dictionary_links audit table
    DB_SERVER: str = "35.224.242.223"
    DB_NAME: str = "MetaPM"
    DB_USER: str = "sqlserver"
    DB_PASSWORD: str = ""
    DB_DRIVER: str = "ODBC Driver 18 for SQL Server"

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: List[str] = ["*", "null"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
