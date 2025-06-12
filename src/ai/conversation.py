from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from schemas.models import ChatConversation, ChatMessage, UserInDB
from sqlalchemy.orm import Session
import uuid

class Conversation(BaseModel):
    id: str = Field(..., description="Unique conversation ID")
    messages: List[Dict] = Field(default_factory=list, description="List of messages in the conversation")
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    context: Dict = Field(default_factory=dict, description="Additional context for the conversation")

class ConversationManager:
    def create_conversation(self, db: Session, user: UserInDB, conversation_id: Optional[str] = None) -> ChatConversation:
        conv_id = uuid.UUID(conversation_id) if conversation_id else uuid.uuid4()
        conversation = ChatConversation(id=conv_id, user_id=user.id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation

    def get_conversation(self, db: Session, user: UserInDB, conversation_id: str) -> Optional[ChatConversation]:
        try:
            conv_id = uuid.UUID(conversation_id)
            return db.query(ChatConversation).filter(ChatConversation.id == conv_id, ChatConversation.user_id == user.id).first()
        except ValueError:
            return None

    def add_message(self, db: Session, user: UserInDB, conversation_id: str, role: str, content: str):
        conversation = self.get_conversation(db, user, conversation_id)
        if not conversation:
            conversation = self.create_conversation(db, user, conversation_id=conversation_id)
        
        message = ChatMessage(conversation_id=conversation.id, role=role, content=content)
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    def get_context(self, db: Session, user: UserInDB, conversation_id: str, max_messages: int = 10) -> List[Dict]:
        conversation = self.get_conversation(db, user, conversation_id)
        if not conversation:
            return []
        
        messages = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation.id).order_by(ChatMessage.timestamp).all()
        recent_messages = messages[-max_messages:]
        return [{"role": m.role, "content": m.content} for m in recent_messages]

    def get_user_conversations(self, db: Session, user: UserInDB) -> List[ChatConversation]:
        return db.query(ChatConversation).filter(ChatConversation.user_id == user.id).all()

    def update_context(self, conversation_id: str, context: Dict):
        # This method is not used in the chat flow, but left for completeness.
        # It might need a db session if it were to be used.
        conversation = self.get_conversation(conversation_id)
        if conversation:
            conversation.context.update(context)
            conversation.last_updated = datetime.now() 