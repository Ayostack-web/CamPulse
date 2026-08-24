from __future__ import annotations

import logging
from contextlib import suppress
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import (
    CurrentUser,
    check_ai_rate_limit,
    check_ai_token_quota,
    get_current_user,
    spend_ai_query,
)
from app.services.pdf import compress_pdf
from app.services.ocr import extract_text_with_tesseract
from app.services.ingestion import ingest_document, search_documents
from app.services.docling_parser import parse_with_docling
from app.services.gemini import chat as gemini_chat, general_chat, GeminiError, error_response
from app.services.rag import build_chunks
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

_STREAM_CHUNK = 1024 * 1024


async def _stream_upload_to_temp(file: UploadFile, suffix: str) -> Path:
    """Copy an upload to a temp file in chunks (never buffers the whole body)."""
    with NamedTemporaryFile(delete=False, suffix=suffix) as out:
        while True:
            chunk = await file.read(_STREAM_CHUNK)
            if not chunk:
                break
            await run_in_threadpool(out.write, chunk)
        return Path(out.name)


class CompressResponse(BaseModel):
    original_name: str
    compressed_name: str
    compressed_path: str


class OcrResponse(BaseModel):
    source_name: str
    extracted_text: str


class IngestResponse(BaseModel):
    document_id: str
    source_name: str
    compressed_path: str
    chunk_count: int
    parser: str
    department_code: str
    summary: str
    questions: list[str]
    tips: list[str]


class SearchHit(BaseModel):
    id: str
    document_id: str
    source_name: str
    chunk_index: int
    text: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHit]


class ParseResponse(BaseModel):
    source_name: str
    document_id: str
    parser: str
    markdown: str
    chunk_count: int
    chunks: list[str]


@router.post("/compress", response_model=CompressResponse)
async def compress_document(file: UploadFile = File(...)) -> CompressResponse:
    suffix = Path(file.filename or "document.pdf").suffix or ".pdf"

    source_path = await _stream_upload_to_temp(file, suffix)

    compressed_path = compress_pdf(source_path)
    return CompressResponse(
        original_name=file.filename or "document.pdf",
        compressed_name=compressed_path.name,
        compressed_path=str(compressed_path),
    )
    


@router.post("/parse", response_model=ParseResponse)
async def parse_document(file: UploadFile = File(...)) -> ParseResponse:
    suffix = Path(file.filename or "document.pdf").suffix.lower() or ".pdf"

    source_path = await _stream_upload_to_temp(file, suffix)

    try:
        parsed_document = parse_with_docling(
            source_path,
            document_id=Path(file.filename or source_path.name).stem,
            source_name=file.filename or source_path.name,
        )
        chunks = build_chunks(parsed_document.markdown)
        return ParseResponse(
            source_name=file.filename or "document.txt",
            document_id=parsed_document.document_id,
            parser=str(parsed_document.metadata.get("parser", "unknown")),
            markdown=parsed_document.markdown,
            chunk_count=len(chunks),
            chunks=chunks,
        )
    finally:
        with suppress(FileNotFoundError):
            source_path.unlink()


@router.post("/ingest", response_model=IngestResponse)
async def ingest_uploaded_document(
    file: UploadFile = File(...),
    department_code: str = Query(default="COLPHY")
) -> IngestResponse:
    suffix = Path(file.filename or "document.pdf").suffix or ".pdf"

    source_path = await _stream_upload_to_temp(file, suffix)

    try:
        result = ingest_document(source_path, department_code=department_code)
        return IngestResponse(
            document_id=result.document_id,
            source_name=result.source_name,
            compressed_path=result.compressed_path,
            chunk_count=result.chunk_count,
            parser=result.parser,
            department_code=result.department_code,
            summary=result.summary,
            questions=result.questions,
            tips=result.tips,
        )
    finally:
        with suppress(FileNotFoundError):
            source_path.unlink()


@router.get("/search", response_model=SearchResponse)
async def search_document_chunks(query: str, top_k: int = 5) -> SearchResponse:
    results = search_documents(query, top_k=top_k)
    return SearchResponse(
        query=query,
        results=[
            SearchHit(
                id=result.id,
                document_id=result.document_id,
                source_name=result.source_name,
                chunk_index=result.chunk_index,
                text=result.text,
                score=result.score,
            )
            for result in results
        ],
    )


@router.post("/ocr", response_model=OcrResponse)
async def ocr_document(file: UploadFile = File(...)) -> OcrResponse:
    suffix = Path(file.filename or "image.png").suffix or ".png"

    source_path = await _stream_upload_to_temp(file, suffix)

    try:
        extracted_text = extract_text_with_tesseract(source_path)
        return OcrResponse(
            source_name=file.filename or "image.png",
            extracted_text=extracted_text,
        )
    finally:
        with suppress(FileNotFoundError):
            source_path.unlink()


class ChatRequest(BaseModel):
    document_id: str = Field(..., min_length=1, max_length=128)
    query: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    answer: str
    context_chunks: list[str]
    follow_up_questions: list[str]


_vector_store_for_chat = VectorStore()


@router.post("/chat", response_model=ChatResponse)
async def chat_with_document(
    payload: ChatRequest,
    _rate_limit: None = Depends(check_ai_rate_limit),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    # Vector search is sync (psycopg/pgvector) — keep it off the event loop.
    results = await run_in_threadpool(
        _vector_store_for_chat.query,
        payload.query,
        top_k=3,
        document_id=payload.document_id,
    )

    if not results:
        return ChatResponse(
            answer="I couldn't find relevant content in this document to answer your question. Try rephrasing or asking about a different topic.",
            context_chunks=[],
            follow_up_questions=[],
        )

    best = results[0]
    context_chunks = [r.text for r in results]

    # Retrieval found something and Gemini will be invoked — only now spend
    # the query so a miss doesn't burn the user's quota.
    await spend_ai_query(user, db)

    context_text = "\n\n".join(context_chunks)
    try:
        ai_answer = await run_in_threadpool(
            gemini_chat, payload.query, context_text, user_id=user.id
        )
    except GeminiError as exc:
        status_code, detail = error_response(exc)
        raise HTTPException(status_code=status_code, detail=detail)
    answer = ai_answer if ai_answer else best.text[:500]

    follow_up_questions = _generate_follow_ups(best.text, payload.query)

    return ChatResponse(
        answer=answer,
        context_chunks=context_chunks,
        follow_up_questions=follow_up_questions,
    )


def _generate_follow_ups(text: str, query: str) -> list[str]:
    import re
    from collections import Counter

    words = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text.lower())
    stopwords = {
        "the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
        "her", "was", "one", "our", "out", "has", "have", "been", "some",
        "them", "than", "that", "this", "very", "what", "which", "will",
        "with", "your", "from", "they", "been", "said", "each",
    }
    terms = [w for w in words if w not in stopwords and len(w) > 3]
    top_terms = [t for t, _ in Counter(terms).most_common(5)]

    suggestions = []
    for term in top_terms[:3]:
        suggestions.append(f"What does '{term}' mean in this context?")
    if not suggestions:
        suggestions = ["Can you summarize the key points?", "What are the main formulas or concepts?"]

    return suggestions


class GeneralChatMessage(BaseModel):
    role: str
    content: str = Field(..., max_length=4000)


class GeneralChatRequest(BaseModel):
    messages: list[GeneralChatMessage] = Field(..., min_length=1, max_length=20)


class GeneralChatResponse(BaseModel):
    content: str


@router.post("/general-chat", response_model=GeneralChatResponse)
async def general_chat_endpoint(
    payload: GeneralChatRequest,
    _rate_limit: None = Depends(check_ai_rate_limit),
    user: CurrentUser = Depends(check_ai_token_quota),
) -> GeneralChatResponse:
    history_text = "\n".join(
        f"{'Student' if m.role == 'user' else 'Assistant'}: {m.content}"
        for m in payload.messages[-10:]
    )

    try:
        answer = await run_in_threadpool(general_chat, history_text, user_id=user.id)
    except GeminiError as exc:
        status_code, detail = error_response(exc)
        raise HTTPException(status_code=status_code, detail=detail)
    if not answer:
        answer = "I'm having trouble connecting to my knowledge base right now. Please try again in a moment."

    return GeneralChatResponse(content=answer)
