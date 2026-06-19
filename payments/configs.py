from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "payments-service"

    application_fee: float = 0.05

    backend_host: str = "0.0.0.0"
    port: int = 9000

    use_postgres: bool = True
    postgres_user: str = "postgres"
    postgres_password: str = "pass"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "lais_marketplace"
    postgres_schema: str = "payments_db"

    sqlite_db_path: str = "../payments/database.db"

    secret_key: str = "My secret key"
    token_algorithm: str = "HS256"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_publishable_key: str = ""

    redis_url: str = "redis://redis:6379/0"
    redis_result_url: str = "redis://redis:6379/1"
    payment_events_channel: str = "payments.events"


settings = Settings()
