import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer, Float, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.auth.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)   # cifrado Fernet
    email_hash = Column(String(64), unique=True, nullable=False)  # sha256 determinístico
    password_hash = Column(String, nullable=False)
    role = Column(String(20), default="free")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    is_verified = Column(Boolean, default=False)
    otp_hash = Column(String, nullable=True)
    otp_expires = Column(DateTime(timezone=True), nullable=True)
    otp_attempts = Column(Integer, default=0)
    otp_purpose = Column(String, nullable=True)
    otp_token = Column(String, unique=True, nullable=True)
    is_blocked = Column(Boolean, default=False)
    
    query_logs = relationship("QueryLog", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    

class QueryLog(Base):  
    __tablename__ = "query_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ip_address = Column(String(255), nullable=False)  
    user_agent = Column(String(255), nullable=True)
    question = Column(Text, nullable=False)
    rewritten_query = Column(Text, nullable=True)
    response = Column(Text, nullable=False)
    decision = Column(String(255), nullable=False)  
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


class OTPLog(Base):
    __tablename__ = "otp_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ip_address = Column(String(255), nullable=False)  
    email = Column(String(255), nullable=True)        
    purpose = Column(String(50), nullable=True)        
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AccessLog(Base):
    __tablename__ = "access_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ip_address = Column(String(255), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    method = Column(String(10), nullable=False) 
    endpoint = Column(String(255), nullable=False)
    status_code = Column(Integer, nullable=False)
    user_agent = Column(String(255), nullable=True)
    referer = Column(String(255), nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    cf_country = Column(String(2), nullable=True)

    __table_args__ = (
        Index('idx_access_logs_ip', 'ip_address'),
        Index('idx_access_logs_timestamp', 'timestamp'),
        Index('idx_access_logs_endpoint', 'endpoint'),
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jti = Column(String(36), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revoked = Column(Boolean, default=False)
    
    user = relationship("User", back_populates="refresh_tokens")


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=True)  
    message = Column(Text, nullable=False)
    ip_address = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_registered = Column(Boolean, default=False)