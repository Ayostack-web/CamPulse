from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import check_ai_token_quota, CurrentUser, get_current_user
from app.models import FlashcardDeck, Flashcard
from app.services.vector_store import VectorStore
from app.services.gemini import chat as gemini_chat, GeminiError, error_response

router = APIRouter(prefix="/flashcards", tags=["flashcards"])

_vector_store = VectorStore()


# ── Schemas ─────────────────────────────────────────────────────────

class DeckCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    document_id: str | None = None
    course_code: str | None = None


class DeckOut(BaseModel):
    id: str
    title: str
    description: str | None
    document_id: str | None
    course_code: str | None
    card_count: int
    created_at: str
    updated_at: str


class CardCreate(BaseModel):
    front: str = Field(..., min_length=1, max_length=2000)
    back: str = Field(..., min_length=1, max_length=2000)


class CardOut(BaseModel):
    id: str
    front: str
    back: str
    ease_factor: float
    interval_days: int
    next_review: str | None
    review_count: int


class BulkCardCreate(BaseModel):
    cards: list[CardCreate] = Field(..., min_length=1, max_length=50)


class GenerateRequest(BaseModel):
    document_id: str = Field(..., min_length=1, max_length=128)
    title: str = Field(default="Generated Flashcards", max_length=200)
    count: int = Field(default=8, ge=2, le=20)


class ReviewRequest(BaseModel):
    card_id: str
    quality: int = Field(..., ge=0, le=3)  # 0=again, 1=hard, 2=good, 3=easy


# ── Deck endpoints ──────────────────────────────────────────────────

@router.get("/decks", response_model=list[DeckOut])
async def list_decks(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FlashcardDeck).where(FlashcardDeck.user_id == user.id).order_by(FlashcardDeck.updated_at.desc())
    )
    return [
        DeckOut(
            id=d.id, title=d.title, description=d.description,
            document_id=d.document_id, course_code=d.course_code,
            card_count=d.card_count,
            created_at=str(d.created_at), updated_at=str(d.updated_at),
        )
        for d in result.scalars().all()
    ]


@router.post("/decks", response_model=DeckOut)
async def create_deck(
    payload: DeckCreate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deck = FlashcardDeck(
        user_id=user.id,
        title=payload.title,
        description=payload.description,
        document_id=payload.document_id,
        course_code=payload.course_code,
    )
    db.add(deck)
    await db.flush()
    return DeckOut(
        id=deck.id, title=deck.title, description=deck.description,
        document_id=deck.document_id, course_code=deck.course_code,
        card_count=0,
        created_at=str(deck.created_at), updated_at=str(deck.updated_at),
    )


@router.get("/decks/{deck_id}", response_model=DeckOut)
async def get_deck(
    deck_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FlashcardDeck).where(FlashcardDeck.id == deck_id, FlashcardDeck.user_id == user.id)
    )
    deck = result.scalar_one_or_none()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return DeckOut(
        id=deck.id, title=deck.title, description=deck.description,
        document_id=deck.document_id, course_code=deck.course_code,
        card_count=deck.card_count,
        created_at=str(deck.created_at), updated_at=str(deck.updated_at),
    )


@router.delete("/decks/{deck_id}")
async def delete_deck(
    deck_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FlashcardDeck).where(FlashcardDeck.id == deck_id, FlashcardDeck.user_id == user.id)
    )
    deck = result.scalar_one_or_none()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    await db.delete(deck)
    return {"ok": True}


# ── Card endpoints ──────────────────────────────────────────────────

@router.get("/decks/{deck_id}/cards", response_model=list[CardOut])
async def list_cards(
    deck_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FlashcardDeck).where(FlashcardDeck.id == deck_id, FlashcardDeck.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Deck not found")

    cards_result = await db.execute(
        select(Flashcard).where(Flashcard.deck_id == deck_id).order_by(Flashcard.created_at)
    )
    return [
        CardOut(
            id=c.id, front=c.front, back=c.back,
            ease_factor=c.ease_factor, interval_days=c.interval_days,
            next_review=str(c.next_review) if c.next_review else None,
            review_count=c.review_count,
        )
        for c in cards_result.scalars().all()
    ]


@router.post("/decks/{deck_id}/cards", response_model=CardOut)
async def add_card(
    deck_id: str,
    payload: CardCreate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FlashcardDeck).where(FlashcardDeck.id == deck_id, FlashcardDeck.user_id == user.id)
    )
    deck = result.scalar_one_or_none()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    card = Flashcard(deck_id=deck_id, front=payload.front, back=payload.back)
    db.add(card)
    deck.card_count += 1
    await db.flush()
    return CardOut(
        id=card.id, front=card.front, back=card.back,
        ease_factor=card.ease_factor, interval_days=card.interval_days,
        next_review=None, review_count=0,
    )


@router.post("/decks/{deck_id}/cards/bulk", response_model=list[CardOut])
async def add_cards_bulk(
    deck_id: str,
    payload: BulkCardCreate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FlashcardDeck).where(FlashcardDeck.id == deck_id, FlashcardDeck.user_id == user.id)
    )
    deck = result.scalar_one_or_none()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    created = []
    for c in payload.cards:
        card = Flashcard(deck_id=deck_id, front=c.front, back=c.back)
        db.add(card)
        created.append(card)
    deck.card_count += len(created)
    await db.flush()
    return [
        CardOut(
            id=c.id, front=c.front, back=c.back,
            ease_factor=c.ease_factor, interval_days=c.interval_days,
            next_review=None, review_count=0,
        )
        for c in created
    ]


@router.delete("/cards/{card_id}")
async def delete_card(
    card_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Flashcard).join(FlashcardDeck).where(
            Flashcard.id == card_id, FlashcardDeck.user_id == user.id
        )
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    deck_result = await db.execute(select(FlashcardDeck).where(FlashcardDeck.id == card.deck_id))
    deck = deck_result.scalar_one_or_none()
    if deck and deck.card_count > 0:
        deck.card_count -= 1
    await db.delete(card)
    return {"ok": True}


# ── Review (spaced repetition) ─────────────────────────────────────

@router.post("/review")
async def review_card(
    payload: ReviewRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Flashcard).join(FlashcardDeck).where(
            Flashcard.id == payload.card_id, FlashcardDeck.user_id == user.id
        )
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    q = payload.quality
    ef = card.ease_factor

    # SM-2 algorithm
    if q < 2:
        card.interval_days = 1
    elif card.interval_days == 0:
        card.interval_days = 1
    elif card.interval_days == 1:
        card.interval_days = 3
    else:
        card.interval_days = round(card.interval_days * ef)

    card.ease_factor = max(1.3, ef + (0.1 - (3 - q) * (0.08 + (3 - q) * 0.02)))
    card.next_review = datetime.now(timezone.utc) + timedelta(days=card.interval_days)
    card.review_count += 1
    card.last_reviewed_at = datetime.now(timezone.utc)

    await db.flush()
    return {
        "ok": True,
        "next_review": str(card.next_review),
        "interval_days": card.interval_days,
        "ease_factor": round(card.ease_factor, 2),
    }


@router.get("/review/due", response_model=list[CardOut])
async def get_due_cards(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(Flashcard)
        .join(FlashcardDeck)
        .where(
            FlashcardDeck.user_id == user.id,
            (Flashcard.next_review <= now) | (Flashcard.next_review.is_(None)),
        )
        .order_by(Flashcard.next_review.asc().nullsfirst())
        .limit(50)
    )
    return [
        CardOut(
            id=c.id, front=c.front, back=c.back,
            ease_factor=c.ease_factor, interval_days=c.interval_days,
            next_review=str(c.next_review) if c.next_review else None,
            review_count=c.review_count,
        )
        for c in result.scalars().all()
    ]


# ── AI Generation ───────────────────────────────────────────────────

@router.post("/generate")
async def generate_flashcards(
    payload: GenerateRequest,
    user: CurrentUser = Depends(check_ai_token_quota),
    db: AsyncSession = Depends(get_db),
):
    results = await run_in_threadpool(
        _vector_store.query, "key concepts definitions formulas", top_k=5
    )
    doc_results = [r for r in results if r.document_id == payload.document_id]
    relevant = doc_results if doc_results else results[:3]

    if not relevant:
        raise HTTPException(status_code=404, detail="No content found for this document. Make sure the document has been processed.")

    context = "\n\n".join(r.text for r in relevant)
    prompt = (
        f"Create exactly {payload.count} flashcards from this academic material. "
        "Each flashcard should test a single concept, definition, or formula.\n\n"
        "Return ONLY a JSON array with objects containing 'front' (the question/prompt) and "
        "'back' (the answer). The front should be concise (1-2 sentences). "
        "The back should be clear and complete but brief.\n\n"
        "Material context:\n"
        f"{context[:4000]}"
    )

    try:
        response = await run_in_threadpool(
            gemini_chat,
            prompt,
            "You are an expert academic flashcard generator. Create precise, study-effective flashcards.",
            user_id=user.id,
            feature="flashcards",
        )
    except GeminiError as exc:
        status_code, detail = error_response(exc)
        raise HTTPException(status_code=status_code, detail=detail)
    if not response:
        raise HTTPException(status_code=500, detail="AI generation failed. Please try again.")

    import json, re
    cleaned = re.sub(r"```json\s*|\s*```", "", response.strip())
    try:
        cards_data = json.loads(cleaned)
        if not isinstance(cards_data, list):
            raise ValueError("Not a list")
    except (json.JSONDecodeError, ValueError):
        # Try to extract JSON array from response
        match = re.search(r"\[.*\]", response, re.DOTALL)
        if match:
            cards_data = json.loads(match.group())
        else:
            raise HTTPException(status_code=500, detail="Failed to parse AI response. Please try again.")

    # Create deck + cards
    deck = FlashcardDeck(
        user_id=user.id,
        title=payload.title,
        document_id=payload.document_id,
    )
    db.add(deck)
    await db.flush()

    created = []
    for item in cards_data[:payload.count]:
        card = Flashcard(
            deck_id=deck.id,
            front=str(item.get("front", ""))[:2000],
            back=str(item.get("back", ""))[:2000],
        )
        db.add(card)
        created.append(card)

    deck.card_count = len(created)
    await db.flush()

    return {
        "deck": DeckOut(
            id=deck.id, title=deck.title, description=deck.description,
            document_id=deck.document_id, course_code=deck.course_code,
            card_count=deck.card_count,
            created_at=str(deck.created_at), updated_at=str(deck.updated_at),
        ),
        "cards": [
            CardOut(
                id=c.id, front=c.front, back=c.back,
                ease_factor=c.ease_factor, interval_days=c.interval_days,
                next_review=None, review_count=0,
            )
            for c in created
        ],
    }
