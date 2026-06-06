from uuid import uuid4
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    username   = Column(String(50), unique=True, nullable=False, index=True)
    hashed_pwd = Column(String(200), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
