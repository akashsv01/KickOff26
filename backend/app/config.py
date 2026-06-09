from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Default to SQLite for local dev (no Docker/Postgres required)
    database_url: str = "sqlite+aiosqlite:///./kickoff26.db"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080

    data_mode: str = "mock"  # mock | live — fixture seed behavior

    # Live scores: demo (simulated, zero API) | api (API-Football poller)
    live_data_mode: str = "demo"

    api_football_key: str = Field(
        default="",
        validation_alias=AliasChoices("API_FOOTBALL_KEY", "RAPIDAPI_KEY"),
    )
    rapidapi_key: str = ""  # legacy alias — prefer API_FOOTBALL_KEY
    rapidapi_host: str = "v3.football.api-sports.io"
    football_data_api_key: str = ""

    cache_ttl_teams: int = 86400
    cache_ttl_matches: int = 300
    cache_ttl_standings: int = 600

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def is_mock(self) -> bool:
        return self.data_mode.lower() == "mock"

    @property
    def is_demo_live(self) -> bool:
        return self.live_data_mode.lower() == "demo"

    @property
    def is_api_live(self) -> bool:
        return self.live_data_mode.lower() == "api"

    @property
    def effective_api_football_key(self) -> str:
        return self.api_football_key or self.rapidapi_key

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        # Browsers treat localhost and 127.0.0.1 as different origins
        if "http://localhost:3000" in origins and "http://127.0.0.1:3000" not in origins:
            origins.append("http://127.0.0.1:3000")
        if "http://127.0.0.1:3000" in origins and "http://localhost:3000" not in origins:
            origins.append("http://localhost:3000")
        return origins


settings = Settings()
