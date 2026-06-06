"""
app/routers/documents.py
文档上传与管理接口
"""

import uuid
import aiofiles
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.document import Document
from app.routers.auth import CurrentUser, get_current_user  # 复用真实 JWT 依赖

from app.tasks import process_document  # 导入 Celery 任务

settings = get_settings()

ALLOWED_EXTENSIONS = {".pdf", ".txt"}
ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain"}
UPLOAD_DIR = Path(settings.upload_dir)
MAX_FILE_SIZE = settings.max_file_size

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    task_id: str
    document_id: UUID
    filename: str
    file_size: int
    status: str
    message: str

class TaskStatusResponse(BaseModel):
    task_id: str
    document_id: UUID
    filename: str
    status: str
    error_msg: Optional[str] = None
    chunk_count: int
    created_at: str
    updated_at: str

class DocumentItem(BaseModel):
    id: UUID
    original_name: str
    filename: str
    file_size: int
    file_type: str
    task_id: str
    status: str
    chunk_count: int
    created_at: str

    model_config = {"from_attributes": True}

class DocumentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[DocumentItem]


# ─── 工具函数 ─────────────────────────────────────────────────────────────────

def _validate_file(file: UploadFile) -> str:
    """校验类型+扩展名，返回小写扩展名（含点）。"""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"不支持的文件格式 '{ext}'，仅允许：{', '.join(ALLOWED_EXTENSIONS)}",
        )
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"不支持的 Content-Type '{file.content_type}'",
        )
    return ext


async def _save_file(file: UploadFile, dest: Path) -> int:
    """流式写入，边写边校验大小上限，返回实际字节数。"""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    chunk_size = 64 * 1024  # 64 KB

    async with aiofiles.open(dest, "wb") as out:
        while chunk := await file.read(chunk_size):
            total += len(chunk)
            if total > MAX_FILE_SIZE:
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"文件超过大小限制 {MAX_FILE_SIZE // 1024 // 1024} MB",
                )
            await out.write(chunk)
    return total


def _fmt_dt(dt) -> str:
    return dt.isoformat() if dt else ""


# ─── 接口 ─────────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="上传文档（异步处理）",
)
async def upload_document(
    file: UploadFile = File(..., description="PDF 或 TXT 文件"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    上传文件后立即返回 task_id（status=pending），不等待处理完成。
    后续接入 Celery：取消下方注释即可。
    """
    ext = _validate_file(file)

    task_id = str(uuid.uuid4())
    stored_name = f"{task_id}{ext}"
    dest = UPLOAD_DIR / stored_name

    file_size = await _save_file(file, dest)

    doc = Document(
        user_id=current_user.id,
        original_name=file.filename or stored_name,
        filename=stored_name,
        file_size=file_size,
        file_type=ext.lstrip("."),
        task_id=task_id,
        status="pending",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)


    
    process_document.apply_async(
        args=[str(doc.id), str(dest)],
        task_id=task_id,
        retry=False) 


    return UploadResponse(
        task_id=doc.task_id,
        document_id=doc.id,
        filename=doc.original_name,
        file_size=doc.file_size,
        status=doc.status,
        message="文件已接收，正在排队处理",
    )


@router.get(
    "/task/{task_id}",
    response_model=TaskStatusResponse,
    summary="查询处理状态",
)
async def get_task_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(
        select(Document).where(
            Document.task_id == task_id,
            Document.user_id == current_user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="任务不存在或无权访问")

    return TaskStatusResponse(
        task_id=doc.task_id,
        document_id=doc.id,
        filename=doc.original_name,
        status=doc.status,
        error_msg=doc.error_msg,
        chunk_count=doc.chunk_count or 0,
        created_at=_fmt_dt(doc.created_at),
        updated_at=_fmt_dt(doc.updated_at),
    )


@router.get(
    "/",
    response_model=DocumentListResponse,
    summary="文档列表（分页）",
)
async def list_documents(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    status_filter: Optional[str] = Query(None, alias="status",
                                         description="按状态过滤：pending/processing/ready/failed"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    base_q = select(Document).where(Document.user_id == current_user.id)
    if status_filter:
        base_q = base_q.where(Document.status == status_filter)

    total = (await db.execute(
        select(func.count()).select_from(base_q.subquery())
    )).scalar_one()

    rows = (await db.execute(
        base_q
        .order_by(Document.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    items = [
        DocumentItem(
            id=r.id,
            original_name=r.original_name,
            filename=r.filename,
            file_size=r.file_size,
            file_type=r.file_type,
            task_id=r.task_id,
            status=r.status,
            chunk_count=r.chunk_count or 0,
            created_at=_fmt_dt(r.created_at),
        )
        for r in rows
    ]

    return DocumentListResponse(total=total, page=page, page_size=page_size, items=items)
