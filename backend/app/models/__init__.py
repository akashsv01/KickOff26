import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# JSON on SQLite, JSONB on Postgres
JsonField = JSON().with_variant(JSONB, "postgresql")


class MatchStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    POSTPONED = "postponed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    followed_team_ids: Mapped[list] = mapped_column(JsonField, default=list)
    favorite_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), index=True)
    country_region: Mapped[str | None] = mapped_column(String(64))
    preferred_language: Mapped[str | None] = mapped_column(String(16))
    timezone: Mapped[str | None] = mapped_column(String(64))  # IANA zone (country-derived at signup, browser zone for "Other", or user-set)
    daily_digest_opt_in: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    favorite_team: Mapped["Team | None"] = relationship(foreign_keys=[favorite_team_id])
    brackets: Mapped[list["Bracket"]] = relationship(back_populates="user")
    messages: Mapped[list["Message"]] = relationship(back_populates="user")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(8), index=True)
    group_letter: Mapped[str | None] = mapped_column(String(2))
    elo_rating: Mapped[float] = mapped_column(Float, default=1500.0)
    flag_url: Mapped[str | None] = mapped_column(String(500))
    # rezarahiminia API dual IDs
    api_object_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    api_seq_id: Mapped[str | None] = mapped_column(String(16), unique=True, index=True)
    iso2: Mapped[str | None] = mapped_column(String(4))

    roster: Mapped["TeamRoster | None"] = relationship(back_populates="team", uselist=False)
    home_matches: Mapped[list["Match"]] = relationship(
        back_populates="home_team", foreign_keys="Match.home_team_id"
    )
    away_matches: Mapped[list["Match"]] = relationship(
        back_populates="away_team", foreign_keys="Match.away_team_id"
    )


class TeamRoster(Base):
    """Cached Zafronix squad roster per team (fetch once, refresh occasionally)."""

    __tablename__ = "team_rosters"

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    zafronix_slug: Mapped[str | None] = mapped_column(String(120))
    players: Mapped[list] = mapped_column(JsonField, default=list)
    coach: Mapped[str | None] = mapped_column(String(120))
    fetch_status: Mapped[str] = mapped_column(String(16), default="pending")
    error_message: Mapped[str | None] = mapped_column(String(255))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    team: Mapped["Team"] = relationship(back_populates="roster")


class Stadium(Base):
    """World Cup 2026 venue from rezarahiminia /get/stadiums."""

    __tablename__ = "stadiums"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    api_object_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    api_seq_id: Mapped[str | None] = mapped_column(String(16), unique=True, index=True)
    name_en: Mapped[str] = mapped_column(String(200))
    name_fa: Mapped[str | None] = mapped_column(String(200))
    fifa_name: Mapped[str | None] = mapped_column(String(200))
    city_en: Mapped[str | None] = mapped_column(String(100))
    country_en: Mapped[str | None] = mapped_column(String(50))
    capacity: Mapped[int | None] = mapped_column(Integer)
    region: Mapped[str | None] = mapped_column(String(50))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)

    matches: Mapped[list["Match"]] = relationship(back_populates="stadium")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    api_fixture_id: Mapped[int | None] = mapped_column(Integer, index=True)
    # rezarahiminia API dual IDs (_id for live GET /get/game/{_id}, id for seq refs)
    api_object_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
    api_seq_id: Mapped[str | None] = mapped_column(String(16), index=True)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    stadium_id: Mapped[int | None] = mapped_column(ForeignKey("stadiums.id"), index=True)
    matchday: Mapped[str | None] = mapped_column(String(8))
    wc_match_type: Mapped[str | None] = mapped_column(String(32))
    home_score: Mapped[int | None] = mapped_column(Integer)
    away_score: Mapped[int | None] = mapped_column(Integer)
    minute: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, native_enum=False), default=MatchStatus.SCHEDULED
    )
    stage: Mapped[str] = mapped_column(String(50), default="group")
    group_letter: Mapped[str | None] = mapped_column(String(2))
    kickoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    local_date: Mapped[str | None] = mapped_column(String(10))
    kickoff_timezone: Mapped[str | None] = mapped_column(String(64))
    venue: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(50))
    stadium_lat: Mapped[float | None] = mapped_column(Float)
    stadium_lng: Mapped[float | None] = mapped_column(Float)
    events: Mapped[list] = mapped_column(JsonField, default=list)
    win_prob_home: Mapped[float | None] = mapped_column(Float)
    win_prob_draw: Mapped[float | None] = mapped_column(Float)
    win_prob_away: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    home_team: Mapped["Team"] = relationship(back_populates="home_matches", foreign_keys=[home_team_id])
    away_team: Mapped["Team"] = relationship(back_populates="away_matches", foreign_keys=[away_team_id])
    stadium: Mapped["Stadium | None"] = relationship(back_populates="matches")
    rooms: Mapped[list["Room"]] = relationship(back_populates="match")
    timeline_events: Mapped[list["MatchEvent"]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="MatchEvent.minute, MatchEvent.id",
    )
    lineup: Mapped["MatchLineup | None"] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        uselist=False,
    )


class MatchLineup(Base):
    """Durable per-match lineup (fetch-once at ~10 min pre-kickoff)."""

    __tablename__ = "match_lineups"

    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True
    )
    home_formation: Mapped[str | None] = mapped_column(String(16))
    away_formation: Mapped[str | None] = mapped_column(String(16))
    home_coach: Mapped[str | None] = mapped_column(String(120))
    away_coach: Mapped[str | None] = mapped_column(String(120))
    home_xi: Mapped[list] = mapped_column(JsonField, default=list)
    away_xi: Mapped[list] = mapped_column(JsonField, default=list)
    home_bench: Mapped[list] = mapped_column(JsonField, default=list)
    away_bench: Mapped[list] = mapped_column(JsonField, default=list)
    source: Mapped[str] = mapped_column(String(8), default="api")
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetch_attempts: Mapped[int] = mapped_column(Integer, default=0)
    fetch_status: Mapped[str] = mapped_column(String(16), default="ready")
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    match: Mapped["Match"] = relationship(back_populates="lineup")


class MatchEvent(Base):
    """Durable per-match timeline row (source of truth for match detail)."""

    __tablename__ = "match_events"
    __table_args__ = (
        UniqueConstraint(
            "match_id",
            "event_type",
            "minute",
            "team_side",
            "player_name",
            "detail",
            name="uq_match_event_dedup",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    minute: Mapped[int] = mapped_column(Integer, default=0)
    team_side: Mapped[str] = mapped_column(String(8))
    player_name: Mapped[str] = mapped_column(String(120))
    detail: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    match: Mapped["Match"] = relationship(back_populates="timeline_events")


class Bracket(Base):
    __tablename__ = "brackets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200), default="My Bracket")
    mode: Mapped[str] = mapped_column(String(20), default="manual")  # manual | monte_carlo
    picks: Mapped[dict] = mapped_column(JsonField, default=dict)
    champion_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    accuracy_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="brackets")


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    name: Mapped[str] = mapped_column(String(200))
    active_poll: Mapped[dict | None] = mapped_column(JsonField)
    polls: Mapped[list] = mapped_column(JsonField, default=list)
    reactions: Mapped[dict] = mapped_column(JsonField, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    match: Mapped["Match"] = relationship(back_populates="rooms")
    messages: Mapped[list["Message"]] = relationship(back_populates="room")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    username: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(String(20), default="chat")  # chat | system
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    room: Mapped["Room"] = relationship(back_populates="messages")
    user: Mapped["User | None"] = relationship(back_populates="messages")


class ApiCache(Base):
    __tablename__ = "api_cache"
    __table_args__ = (UniqueConstraint("cache_key", name="uq_cache_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(255), index=True)
    payload: Mapped[dict] = mapped_column(JsonField)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
