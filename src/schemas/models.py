from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Date, Time, ForeignKey, Text, Enum, ARRAY
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, date, time
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from sqlalchemy.dialects.postgresql import UUID
import uuid

# Pydantic Schemas for API responses
class ChatMessageSchema(BaseModel):
    id: int
    role: str
    content: str
    timestamp: datetime

    class Config:
        from_attributes = True

class ChatConversationSchema(BaseModel):
    id: uuid.UUID
    user_id: int
    created_at: datetime
    last_updated: datetime
    messages: List[ChatMessageSchema] = []

    class Config:
        from_attributes = True

Base = declarative_base()

# SQLAlchemy ORM Models
class UserInDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    type = Column(String, nullable=False, default="user")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    preferences = relationship("UserPreference", back_populates="user", uselist=False)
    documents = relationship("DocumentInDB", back_populates="user")

class Token(BaseModel):
    access_token: str
    type: str

# ORM model for documents
class DocumentInDB(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("UserInDB", back_populates="documents")

# ORM model for chat conversations
class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")

# ORM model for chat messages
class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("chat_conversations.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    conversation = relationship("ChatConversation", back_populates="messages")

# Pydantic schemas for documents
class DocumentCreate(BaseModel):
    title: str
    content: str

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None

class DocumentSchema(BaseModel):
    id: int
    user_id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
