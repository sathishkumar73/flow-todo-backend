from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    env: str = "development"
    api_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"

    database_url: str

    clerk_publishable_key: str = ""
    clerk_secret_key: str = ""
    clerk_jwks_url: str = ""

    outrank_webhook_token: str = ""
    indexnow_api_key: str = ""

    openai_api_key: str = ""
    enforce_pro_gating: bool = False
    log_level: str = "INFO"

    class Config:
        env_file = ".env"


settings = Settings()
