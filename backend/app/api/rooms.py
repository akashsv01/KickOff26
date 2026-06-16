from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_user
from app.db import get_db
from app.models import Match, Message, Poll, PollVote, Room, User
from app.schemas import (
    MessageCreate,
    MessageResponse,
    PollCreate,
    PollResult,
    PollVoteRequest,
    RoomCreate,
    RoomResponse,
    RoomSummaryItem,
)
from app.services.polls import is_poll_closed, load_room_polls, serialize_one
from app.services.room_reset import clear_room_user_content
from app.websocket.gateway import ws_manager

router = APIRouter(prefix="/rooms", tags=["rooms"])


async def _room_response(
    db: AsyncSession, room: Room, *, user_id: int | None = None
) -> RoomResponse:
    _, polls = await load_room_polls(db, room.id, user_id=user_id)
    participants = ws_manager.room_participants(room.id)
    return RoomResponse(
        id=room.id,
        match_id=room.match_id,
        name=room.name,
        active_poll=polls[0] if polls else None,
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
    return await _room_response(db, room, user_id=user.id if user else None)


@router.get("/match/{match_id}", response_model=list[RoomResponse])
async def rooms_for_match(
    match_id: int,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Room).where(Room.match_id == match_id))
    uid = user.id if user else None
    return [await _room_response(db, r, user_id=uid) for r in result.scalars().all()]


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(
    room_id: int,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return await _room_response(db, room, user_id=user.id if user else None)


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


@router.get("/{room_id}/polls", response_model=list[PollResult])
async def list_polls(
    room_id: int,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """All polls for a room with persisted aggregate results. For an authenticated
    user, each poll also carries `my_vote` (the option they previously chose), so
    results - and their own pick - survive leaving and rejoining the room."""
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    _, polls = await load_room_polls(db, room_id, user_id=user.id if user else None)
    return polls


async def _broadcast_poll(db: AsyncSession, room_id: int, poll: Poll, event: str) -> None:
    """Push aggregate-only results to the room channel. The payload never carries
    any individual user's vote - `my_vote` is omitted (None) for every recipient."""
    _, public = await load_room_polls(db, room_id, user_id=None)
    changed = next((p for p in public if p["id"] == poll.id), None)
    await ws_manager.broadcast(
        ws_manager.room_channel(room_id),
        {"type": event, "poll": changed, "polls": public},
    )


@router.post("/{room_id}/poll", response_model=PollResult)
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
    poll = Poll(
        room_id=room_id,
        question=data.question.strip(),
        options=options,
        created_by=user.username,
        created_by_user_id=user.id,
    )
    db.add(poll)
    await db.flush()
    await _broadcast_poll(db, room_id, poll, "poll_created")
    return await serialize_one(db, poll, user_id=user.id)


@router.post("/{room_id}/polls/{poll_id}/vote", response_model=PollResult)
async def vote_poll(
    room_id: int,
    poll_id: int,
    data: PollVoteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cast or change the authenticated user's vote. Upserts one row per
    (poll, user); re-voting updates the stored option. Returns the updated
    aggregate plus this user's `my_vote`."""
    poll = await db.get(Poll, poll_id)
    if not poll or poll.room_id != room_id:
        raise HTTPException(status_code=404, detail="Poll not found")
    if is_poll_closed(poll):
        raise HTTPException(status_code=400, detail="This poll is closed")
    if data.option_index >= len(poll.options or []):
        raise HTTPException(status_code=400, detail="Invalid option")

    existing = (
        await db.execute(
            select(PollVote).where(
                PollVote.poll_id == poll_id, PollVote.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.option_index = data.option_index
    else:
        db.add(PollVote(poll_id=poll_id, user_id=user.id, option_index=data.option_index))
    await db.flush()

    await _broadcast_poll(db, room_id, poll, "poll_updated")
    return await serialize_one(db, poll, user_id=user.id)


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
