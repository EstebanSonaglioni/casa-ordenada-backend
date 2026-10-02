import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://admin:change-me-locally@localhost:5432/main",
    )
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "")
    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    )
    refresh_token_expire_days: int = int(
        os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
    )
    test_user_username: str = os.getenv("TEST_USER_USERNAME", "")
    test_user_password: str = os.getenv("TEST_USER_PASSWORD", "")
    test_user_role: str = os.getenv("TEST_USER_ROLE", "member")
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:3000")


settings = Settings()
