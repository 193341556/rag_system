from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.database import init_db, close_db



@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()

app = FastAPI(
    title="RAG 智能文档问答系统",
    description="基于 RAG 架构，支持文档上传、语义检索与 LLM 流式问答。",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import auth, documents, chat

app.include_router(auth.router,      prefix="/api/auth",      tags=["认证"])
app.include_router(documents.router, prefix="/api/documents", tags=["文档"])
app.include_router(chat.router,      prefix="/api/chat",      tags=["问答"])

@app.get("/health", tags=["系统"])
async def health_check():
    return {"status": "ok", "version": app.version}