from uuid import uuid4
from typing import Optional
from sqlalchemy import Column, String, DateTime, Integer, BigInteger, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id       = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                           nullable=False, index=True)

    # 原始文件信息
    original_name = Column(String(255), nullable=False)          # 用户上传时的文件名
    filename      = Column(String(255), nullable=False)          # 服务器存储名（uuid + ext）
    file_size     = Column(BigInteger, nullable=False, default=0)
    file_type     = Column(String(10), nullable=False)           # "pdf" | "txt"

    # 任务追踪
    task_id       = Column(String(64), unique=True, nullable=False, index=True)
    status        = Column(String(20), nullable=False, default="pending")
    # pending → processing → ready | failed
    error_msg     = Column(Text, nullable=True)

    # 处理结果
    chunk_count   = Column(Integer, default=0)

    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(),
                           onupdate=func.now())
