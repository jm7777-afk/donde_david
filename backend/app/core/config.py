import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME = "Donde David Restaurant Management System"
    VERSION = "2.0.0"
    API_V1_STR = "/api/v1"
    ALGORITHM = "HS256"
    _DEVELOPMENT_SECRET = "local-only-secret-do-not-use-in-production"

    def __init__(self):
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
        configured_secret = os.getenv("SECRET_KEY")
        if configured_secret is not None:
            configured_secret = configured_secret.strip()
        self.SECRET_KEY = configured_secret or self._DEVELOPMENT_SECRET
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

        database_url = os.getenv("DATABASE_URL", "sqlite:///./restaurante.db").strip()
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        self.DATABASE_URL = database_url
        self.ALLOWED_ORIGINS = os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:8000,http://127.0.0.1:8000"
        )
        self.BCV_RATE_API_URL = os.getenv(
            "BCV_RATE_API_URL",
            "https://ve.dolarapi.com/v1/dolares/oficial"
        ).strip()

        if self.ENVIRONMENT == "production":
            if not configured_secret or len(configured_secret) < 32:
                raise ValueError("Production requires a SECRET_KEY with at least 32 characters.")
            if not database_url.startswith("postgresql+psycopg://"):
                raise ValueError("Production requires a persistent PostgreSQL DATABASE_URL.")
            origins = [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]
            if not origins or "*" in origins:
                raise ValueError("Production requires explicit ALLOWED_ORIGINS; wildcard is not allowed.")
        if self.ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be greater than zero.")

    @property
    def ALLOWED_ORIGINS_LIST(self) -> List[str]:
        if not self.ALLOWED_ORIGINS or self.ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

settings = Settings()
