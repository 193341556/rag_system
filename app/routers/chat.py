from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse
import json, hashlib
from redis import asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embedder import Embedder
from app.services.retriever import HybridRetriever
from app.services.llm_client import ask_llm_stream, ask_llm
from app.limiter import limiter
from app.database import get_db
from app.models.document import Document

router = APIRouter()
embedder = Embedder()

CACHE_TTL = 3600

async def get_redis():
    return await aioredis.from_url('redis://localhost:6379/0')

async def resolve_doc_id(task_id: str, db: AsyncSession) -> str:
    """前端传来的是 task_id，转换成数据库里真实的 doc.id"""
    result = await db.execute(select(Document).where(Document.task_id == task_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return str(doc.id)

@router.get('/stream')
async def stream_answer(doc_id: str, question: str, db: AsyncSession = Depends(get_db)):
    real_id = await resolve_doc_id(doc_id, db)
    retriever = HybridRetriever(real_id, embedder)
    chunks = retriever.retrieve(question, top_k=5)
    context = '\n\n'.join([c.page_content for c in chunks])

    async def event_generator():
        async for token in ask_llm_stream(question, context):
            yield f'data: {json.dumps({"type":"chunk","content":token})}\n\n'
        sources = [{'text': c.page_content[:100]} for c in chunks]
        yield f'data: {json.dumps({"type":"done","sources":sources})}\n\n'

    return StreamingResponse(event_generator(), media_type='text/event-stream')

@router.post('/ask')
@limiter.limit('10/minute')
async def ask(request: Request, doc_id: str, question: str, db: AsyncSession = Depends(get_db)):
    real_id = await resolve_doc_id(doc_id, db)
    cache_question = question.strip()
    redis = await get_redis()
    cache_key = f'qa:{real_id}:{hashlib.md5(cache_question.encode()).hexdigest()}'

    cached = await redis.get(cache_key)
    if cached:
        result = json.loads(cached)
        result['from_cache'] = True
        return result

    retriever = HybridRetriever(real_id, embedder)
    chunks = retriever.retrieve(question, top_k=5)
    context = '\n\n'.join([c.page_content for c in chunks])
    answer = await ask_llm(question, context)

    result = {'answer': answer, 'from_cache': False}
    await redis.setex(cache_key, CACHE_TTL, json.dumps({'answer': answer}))
    return result