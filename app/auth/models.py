import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.auth.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String(20), default="free")
    is_active = Column(Boolean, default=True)    
    created_at = Column(DateTime(timezone=True), server_default=func.now())    
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    query_logs = relationship("QueryLog", back_populates="user", cascade="all, delete-orphan")


class QueryLog(Base):  
    __tablename__ = "query_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ip_address = Column(String(50), nullable=False)
    user_agent = Column(String(255), nullable=True)
    question = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    decision = Column(String(50), nullable=False)  
    tokens_generated = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    endpoint = Column(String(50), nullable=False)
    model_used = Column(String(100), nullable=True)  
    temperature = Column(Float, nullable=True)
    top_k_retrieved = Column(Integer, nullable=True)     
    qa_cache_score = Column(Float, nullable=True)  
    retrieval_score = Column(Float, nullable=True)  
    grounding_score = Column(Float, nullable=True)  
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="query_logs")