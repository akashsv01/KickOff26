from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_user
from app.db import get_db
from app.models import Match, Message, Room, User
from app.schemas import (
    MessageCreate,
    MessageResponse,
    PollCreate,
    PollResponse,
    RoomCreate,
    RoomResponse,
    RoomSummaryItem,
)
from app.services.room_live import (
    apply_vote,
    broadcast_presence,
    normalize_polls,
    new_poll_id,
    serialize_poll,
    voter_key,
)
from app.services.room_reset import clear_room_user_content
from app.websocket.gateway import ws_manager

router = APIRouter(prefix="/rooms", tags=["rooms"])


def _room_response(room: Room) -> RoomResponse:
    polls_raw = normalize_polls(room)
    polls = [PollResponse(**serialize_poll(p)) for p in polls_raw]
    participants = ws_manager.room_participants(room.id)
    return RoomResponse(
        id=room.id,
        match_id=room.match_id,
        name=room.name,
        active_poll=serialize_poll(polls_raw[0]) if polls_raw else None,
        polls=polls,
        reactions=dict(room.reactions or {}),
        watcher_count=len(participants),
        participants=participants,
    )


@router.get("/summary", response_model=list[RoomSummaryItem])
async def room_summary(db: AsyncSession = Depends(get_db)):
    """Primary room per match with live watcher counts for the room browser."""
    result = await db.execute(select(Room).order_by(Room.match_id, Room.id))
    rooms = result.scalars().all()
    seen_matches: set[int] = set()
    summary: list[RoomSummaryItem] = []
    for room in rooms:
        if room.match_id in seen_matches:
            continue
        seen_matches.add(room.match_id)
        summary.append(
            RoomSummaryItem(
                match_id=room.match_id,
                room_id=room.id,
                watcher_count=ws_manager.room_watcher_count(room.id),
            )
        )
    return summary


@router.post("/reset-content")
async def reset_room_content(db: AsyncSession = Depends(get_db)):
    """Clear all room chat, reactions, and polls. Dev/admin maintenance — re-runnable."""
    result = await clear_room_user_content(db)
    await db.commit()
    return result


@router.post("", response_model=RoomResponse)
async def create_room(
    data: RoomCreate,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    match = await db.get(Match, data.match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    name = data.name or f"Watch Room - Match {data.match_id}"
    room = Room(match_id=data.match_id, name=name, reactions={}, polls=[])
    db.add(room)
    await db.flush()
    return _room_response(room)


@router.get("/match/{match_id}", response_model=list[RoomResponse])
async def rooms_for_match(match_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Room).where(Room.match_id == match_id))
    return [_room_response(r) for r in result.scalars().all()]


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(room_id: int, db: AsyncSession = Depends(get_db)):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return _room_response(room)


# Chat is capped to the most recent events (chat + join/leave interleaved).
ROOM_HISTORY_LIMIT = 20


@router.get("/{room_id}/messages", response_model=list[MessageResponse])
async def get_messages(room_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message)
        .where(Message.room_id == room_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(ROOM_HISTORY_LIMIT)
    )
    msgs = list(reversed(result.scalars().all()))
    return [MessageResponse.model_validate(m) for m in msgs]


@router.post("/{room_id}/messages", response_model=MessageResponse)
async def post_message(
    room_id: int,
    data: MessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    content = data.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    msg = Message(
        room_id=room_id,
        user_id=user.id,
        username=user.username,
        content=content,
    )
    db.add(msg)
    await db.flush()

    await ws_manager.broadcast(
        ws_manager.room_channel(room_id),
        {
            "type": "new_message",
            "message": MessageResponse.model_validate(msg).model_dump(mode="json"),
        },
    )
    return MessageResponse.model_validate(msg)


@router.post("/{room_id}/poll")
async def create_poll(
    room_id: int,
    data: PollCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    options = [opt.strip() for opt in data.options if opt.strip()]
    if len(options) < 2:
        raise HTTPException(status_code=400, detail="At least two options required")
    poll = {
        "id": new_poll_id(),
        "question": data.question.strip(),
        "options": {opt: 0 for opt in options},
        "votes": {},
        "created_by": user.username,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    polls = [poll, *normalize_polls(room)]
    room.polls = polls
    room.active_poll = poll
    await db.flush()
    serialized = serialize_poll(poll)
    await ws_manager.broadcast(
        ws_manager.room_channel(room_id),
        {"type": "poll_created", "poll": serialized, "polls": [serialize_poll(p) for p in polls]},
    )
    return serialized


@router.post("/{room_id}/poll/vote")
async def vote_poll(
    room_id: int,
    option: str,
    poll_id: str | None = Query(default=None),
    guest_id: str | None = Query(default=None),
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    polls = normalize_polls(room)
    if not polls:
        raise HTTPException(status_code=404, detail="No polls in this room")
    target = polls[0] if not poll_id else next((p for p in polls if p.get("id") == poll_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Poll not found")
    key = voter_key(user.id if user else None, guest_id)
    try:
        apply_vote(target, option, key)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid option")
    room.polls = polls
    room.active_poll = polls[0]
    await db.flush()
    serialized = [serialize_poll(p) for p in polls]
    await ws_manager.broadcast(
        ws_manager.room_channel(room_id),
        {"type": "poll_updated", "poll": serialize_poll(target), "polls": serialized},
    )
    return serialize_poll(target)


@router.post("/{room_id}/reactions")
async def add_reaction(
    room_id: int,
    emoji: str,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    emoji = emoji.strip()
    if not emoji:
        raise HTTPException(status_code=400, detail="Emoji required")
    reactions = dict(room.reactions or {})
    reactions[emoji] = reactions.get(emoji, 0) + 1
    room.reactions = reactions
    await db.flush()
    username = user.username if user else "guest"
    await ws_manager.broadcast(
        ws_manager.room_channel(room_id),
        {
            "type": "reaction_updated",
            "reactions": reactions,
            "emoji": emoji,
        },
    )
    await ws_manager.broadcast(
        ws_manager.room_channel(room_id),
        {
            "type": "reaction_burst",
            "emoji": emoji,
            "username": username,
        },
    )
    return reactions
