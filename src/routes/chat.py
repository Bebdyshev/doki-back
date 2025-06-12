from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.security import OAuth2PasswordBearer
from typing import Optional, List
from ai.agent import AIAgent, ChatRequest, ChatResponse, Message
from ai.conversation import ConversationManager
import uuid
from auth_utils import verify_access_token
from sqlalchemy.orm import Session
from config import get_db
from schemas.models import UserInDB, ChatConversationSchema, ChatMessageSchema, ChatConversation
from pydantic import BaseModel

class UserChatRequest(BaseModel):
    messages: List[Message]

class ChatApiResponse(BaseModel):
    response: str
    conversation_id: str
    tool_output: Optional[List[dict]]

router = APIRouter()
conversation_manager = ConversationManager()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = verify_access_token(token)
    if payload is None or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    
    user_email = payload["sub"]
    user = db.query(UserInDB).filter(UserInDB.email == user_email).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("/", response_model=ChatApiResponse)
async def chat(
    request: UserChatRequest,
    conversation_id: Optional[str] = Query(None),
    model: Optional[str] = Query(None, description="Optional Groq model ID"),
    user: UserInDB = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            # Create a new conversation in the DB and associate it with the user
            conversation_manager.create_conversation(db, user, conversation_id)
        
        # Add user message to conversation history
        for message in request.messages:
            conversation_manager.add_message(db, user, conversation_id, message.role, message.content)
        
        context_messages = conversation_manager.get_context(db, user, conversation_id)
        
        # Instantiate agent (allows dynamic model selection)
        agent = AIAgent(model_name=model)

        # Prepare request for the agent
        agent_request = ChatRequest(messages=context_messages)
        
        # Get response from the agent
        agent_response = await agent.chat(agent_request, db)
        
        # Add assistant's response to conversation history
        conversation_manager.add_message(db, user, conversation_id, "assistant", agent_response.response)
        
        return ChatApiResponse(response=agent_response.response, conversation_id=conversation_id, tool_output=agent_response.tool_output)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/conversations", response_model=List[ChatConversationSchema])
async def get_user_conversations(user: UserInDB = Depends(get_current_user), db: Session = Depends(get_db)):
    return conversation_manager.get_user_conversations(db, user)

@router.get("/conversation/{conversation_id}", response_model=ChatConversationSchema)
async def get_conversation(conversation_id: str, user: UserInDB = Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = conversation_manager.get_conversation(db, user, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation 