from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.database_url import normalize_database_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Default to SQLite for local dev (no Docker/Postgres required)
    database_url: str = Field(
        default="sqlite+aiosqlite:///./kickoff26.db",
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080

    data_mode: str = "mock"  # mock | live - fixture seed behavior

    # Live scores: demo (simulated, zero API) | api (API-Football poller)
    live_data_mode: str = "demo"

    api_football_key: str = Field(
        default="",
        validation_alias=AliasChoices("API_FOOTBALL_KEY", "RAPIDAPI_KEY"),
    )
    rapidapi_key: str = ""  # legacy alias - prefer API_FOOTBALL_KEY
    rapidapi_host: str = "v3.football.api-sports.io"
    football_data_api_key: str = ""

    # rezarahiminia World Cup 2026 API (https://worldcup26.ir) - live data source
    worldcup_api_token: str = ""  # JWT bearer token (valid ~84 days)
    worldcup_api_base: str = "https://worldcup26.ir"
    # Optional credentials used only by scripts/get_worldcup_token.py
    worldcup_api_email: str = ""
    worldcup_api_password: str = ""

    # Zafronix squad rosters (https://api.zafronix.com)
    zafronix_api_key: str = ""
    zafronix_api_base: str = "https://api.zafronix.com"
    zafronix_roster_fresh_hours: int = 168
    zafronix_roster_retry_hours: int = 24
    zafronix_request_timeout: float = 20.0
    zafronix_prefetch_interval_seconds: int = 120
    # Manual-only live Zafronix roster fetch (default off — squads come from bundled JSON).
    zafronix_live_fetch_enabled: bool = False

    # rezarahiminia live poller cadence (single shared backend poller)
    worldcup_poll_live_seconds: int = 25
    worldcup_poll_pre_kickoff_seconds: int = 30
    worldcup_poll_idle_max_seconds: int = 300
    worldcup_groups_refresh_every: int = 10
    worldcup_rate_limit_per_minute: int = 500
    worldcup_rate_limit_window_seconds: int = 60
    worldcup_rate_limit_warn_at: int = 400
    worldcup_rate_limit_backoff_at: int = 450

    cache_ttl_teams: int = 86400
    cache_ttl_matches: int = 300
    cache_ttl_standings: int = 600

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Groq AI tournament assistant (https://console.groq.com)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_max_tokens: int = 1024

    # Transactional email (Resend - https://resend.com)
    resend_api_key: str = ""
    # Verified sender once the domain is set up in Resend (hello@kickoff2026.tech);
    # until then Resend's onboarding@resend.dev sandbox sender works for testing.
    from_email: str = "KickOff26 <onboarding@resend.dev>"
    # Public app URL used for links/branding in emails.
    app_base_url: str = "https://kickoff2026.tech"
    # Public URL of the KickOff26 logo/trophy icon shown in email headers.
    # Defaults to the app's PWA icon; override if hosted elsewhere.
    email_logo_url: str = ""
    # Guards the in-process APScheduler digest loop (option a). Leave off when a
    # standalone scheduled job runs `python -m app.jobs.daily_digest` (option b).
    enable_digest_scheduler: bool = False

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> str:
        if value is None:
            return "sqlite+aiosqlite:///./kickoff26.db"
        return normalize_database_url(str(value).strip())

    @field_validator("groq_api_key", mode="before")
    @classmethod
    def strip_groq_key(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @property
    def has_groq_key(self) -> bool:
        return bool(self.groq_api_key.strip())

    @property
    def has_resend_key(self) -> bool:
        return bool(self.resend_api_key.strip())

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
    def has_worldcup_token(self) -> bool:
        return bool(self.worldcup_api_token)

    @property
    def has_zafronix_key(self) -> bool:
        return bool(self.zafronix_api_key)

    @property
    def zafronix_live_fetch(self) -> bool:
        """True when background/on-demand Zafronix HTTP fetches are allowed."""
        return self.zafronix_live_fetch_enabled and self.has_zafronix_key

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
