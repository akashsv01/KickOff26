from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, computed_field, field_validator

from app.data.country_timezones import resolve_timezone

ALLOWED_LANGUAGES = frozenset({"en", "es", "fr", "de", "pt", "ar", "zh", "ja", "ko", "it", "nl"})


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6)
    favorite_team_id: int
    country_region: str | None = Field(default=None, max_length=64)
    preferred_language: str | None = Field(default=None, max_length=16)
    timezone: str | None = Field(default=None, max_length=64)
    followed_team_ids: list[int] = Field(default_factory=list, max_length=8)

    @field_validator("country_region")
    @classmethod
    def strip_country(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("timezone")
    @classmethod
    def strip_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("preferred_language")
    @classmethod
    def normalize_language(cls, value: str | None) -> str | None:
        if value is None or not str(value).strip():
            return None
        lang = str(value).strip().lower()
        if lang not in ALLOWED_LANGUAGES:
            raise ValueError(f"Language must be one of: {', '.join(sorted(ALLOWED_LANGUAGES))}")
        return lang

    @field_validator("followed_team_ids")
    @classmethod
    def dedupe_follows(cls, value: list[int]) -> list[int]:
        return list(dict.fromkeys(value))


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    followed_team_ids: list[int] = []
    favorite_team_id: int | None = None
    country_region: str | None = None
    preferred_language: str | None = None
    timezone: str | None = None

    model_config = {"from_attributes": True}

    @computed_field  # type: ignore[prop-decorator]
    @property
    def resolved_timezone(self) -> str:
        """Effective display zone: explicit timezone -> country map -> UTC.

        Mirrors backend resolve_timezone(user) so the frontend never has to
        replicate the country map and never falls back to UTC for a known
        country (e.g. India -> Asia/Kolkata).
        """
        return resolve_timezone(self)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserProfileResponse(BaseModel):
    """Full account view for the authenticated user (/api/users/me)."""

    id: int
    username: str
    email: str
    country: str | None = None  # stored as User.country_region
    timezone: str | None = None
    daily_digest_opt_in: bool = False
    created_at: datetime | None = None


class UserUpdate(BaseModel):
    """Self-service profile edit. Every field optional - only provided ones change."""

    username: str | None = Field(default=None, min_length=3, max_length=100)
    email: EmailStr | None = None
    country: str | None = Field(default=None, max_length=64)
    timezone: str | None = Field(default=None, max_length=64)
    password: str | None = Field(default=None, min_length=6)
    current_password: str | None = None  # required when changing password
    daily_digest_opt_in: bool | None = None

    @field_validator("username", "country", "timezone")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class AccountDeleteRequest(BaseModel):
    password: str = Field(min_length=1)


class TeamResponse(BaseModel):
    id: int
    name: str
    code: str
    group_letter: str | None = None
    elo_rating: float
    flag_url: str | None = None

    model_config = {"from_attributes": True}


class SquadPlayerResponse(BaseModel):
    jersey: int | None = None
    name: str
    position: str
    club: str | None = None
    is_captain: bool = False


class SquadBlockResponse(BaseModel):
    status: str
    players_by_position: dict[str, list[SquadPlayerResponse]] = {}
    fetched_at: str | None = None


class PlayerToWatchResponse(BaseModel):
    player: str
    reason: str
    image_url: str | None = None


class TeamProfileResponse(BaseModel):
    team: TeamResponse
    coach: str | None = None
    coach_source: str | None = None
    coach_display: str
    squad: SquadBlockResponse
    player_to_watch: PlayerToWatchResponse | None = None


class MatchEvent(BaseModel):
    type: str
    minute: int
    team_id: int | None = None
    player: str | None = None


class MatchResponse(BaseModel):
    id: int
    home_team: TeamResponse
    away_team: TeamResponse
    home_score: int | None = None
    away_score: int | None = None
    minute: int | None = None
    status: str
    stage: str
    group_letter: str | None = None
    kickoff_at: datetime | None = None
    venue: str | None = None
    city: str | None = None
    country: str | None = None
    events: list = []
    win_prob_home: float | None = None
    win_prob_draw: float | None = None
    win_prob_away: float | None = None

    model_config = {"from_attributes": True}


class WinProbabilities(BaseModel):
    home: float
    draw: float
    away: float


class BracketPickRequest(BaseModel):
    match_key: str
    winner_team_id: int


class BracketSaveRequest(BaseModel):
    name: str = "My Bracket"
    picks: dict


class BracketResponse(BaseModel):
    id: int
    name: str
    mode: str
    picks: dict
    champion_team_id: int | None = None
    accuracy_score: float | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class BracketPicksResponse(BaseModel):
    picks: dict
    updated_at: datetime | None = None


class SimulateRequest(BaseModel):
    iterations: int = Field(default=1000, ge=100, le=50000)


class SimulationResult(BaseModel):
    team_stats: dict
    most_likely_bracket: dict
    iterations: int


class ItineraryRequest(BaseModel):
    team_ids: list[int]
    max_cities: int = Field(default=5, ge=1, le=16)
    budget_usd: float | None = None


class TicketEstimate(BaseModel):
    low_usd: int
    high_usd: int
    label: str
    display_range: str
    is_estimate: bool = True


class ItineraryStop(BaseModel):
    city: str
    country: str
    match_id: int
    match_label: str
    stadium: str
    stage: str = "group"
    kickoff_at: datetime | None
    lat: float
    lng: float
    travel_from_prev_km: float | None = None
    travel_from_prev_hours: float | None = None
    travel_is_estimate: bool = False
    ticket_estimate: TicketEstimate
    cross_border_note: str | None = None


class ItineraryResponse(BaseModel):
    stops: list[ItineraryStop]
    total_ticket_cost_low_usd: int
    total_ticket_cost_high_usd: int
    total_travel_hours: float
    total_travel_km: float
    disclaimer: str
    notes: list[str]
    total_cost_usd: float = 0


class RoomCreate(BaseModel):
    match_id: int
    name: str | None = None


class PollResponse(BaseModel):
    id: str
    question: str
    options: dict[str, int]
    votes: dict[str, str] = {}
    created_by: str = ""
    created_at: str | None = None


class RoomResponse(BaseModel):
    id: int
    match_id: int
    name: str
    active_poll: dict | None = None
    polls: list[PollResponse] = []
    reactions: dict = {}
    watcher_count: int = 0
    participants: list[dict] = []

    model_config = {"from_attributes": True}


class RoomSummaryItem(BaseModel):
    match_id: int
    room_id: int
    watcher_count: int


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class MessageResponse(BaseModel):
    id: int
    room_id: int
    username: str
    content: str
    message_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PollCreate(BaseModel):
    question: str = Field(min_length=1, max_length=300)
    options: list[str] = Field(min_length=2, max_length=6)


class FollowTeamsRequest(BaseModel):
    team_ids: list[int]
