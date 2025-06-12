from fastapi import APIRouter
from pydantic import BaseModel
import os
from pydantic_ai import Agent
from pydantic_ai.models.groq import GroqModel

router = APIRouter()

# Pydantic models for request/response
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

# Set up the Groq agent
model = GroqModel("llama-3-70b-8192")
agent = Agent(model)

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    result = await agent.run(request.message)
    # result is a RunResult, get the text from the last message
    text = result.text if hasattr(result, "text") else str(result)
    return ChatResponse(response=text)
