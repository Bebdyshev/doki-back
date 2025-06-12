from typing import List, Optional, Any
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from langchain.tools import tool
from sqlalchemy.orm import Session
from datetime import datetime

# New imports for SerpAPI and DB docs
from schemas.models import DocumentInDB
import requests

load_dotenv()

global_db: Optional[Session] = None

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

class ChatResponse(BaseModel):
    response: str
    tool_output: Optional[Any] = None

class AIAgent:
    def __init__(self, model_name: Optional[str] = None):
        """Initialize the agent with optional custom LLM model."""
        model_name = model_name or os.environ.get(
            "GROQ_DEFAULT_MODEL",
            "meta-llama/llama-4-maverick-17b-128e-instruct",
        )

        self.llm = ChatGroq(
            model=model_name,
            temperature=float(os.environ.get("LLM_TEMPERATURE", 0.7)),
            groq_api_key=os.environ.get("GROQ_API_KEY"),
        )
        self.prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are a helpful assistant for a document management application.\n\nYour tasks include:\n• Answering user questions.\n• Using google_search_tool for up-to-date external information when appropriate.\n• Using knowledge_base_tool to retrieve stored document content when relevant.\n\nThink step-by-step, decide if a tool is needed, then call exactly one tool when useful. Return friendly responses that cite any tool information you used.""",
            ),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])

    async def chat(self, request: ChatRequest, db: Session) -> ChatResponse:
        global global_db
        global_db = db
        tools = [google_search_tool, knowledge_base_tool]
        agent = create_tool_calling_agent(self.llm, tools, self.prompt)
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, return_intermediate_steps=True)
        chat_history = []
        for msg in request.messages[:-1]:
            chat_history.append(HumanMessage(content=msg.content) if msg.role == "user" else AIMessage(content=msg.content))
        user_input = request.messages[-1].content
        response = await agent_executor.ainvoke(
            {
                "input": user_input,
                "chat_history": chat_history,
            }
        )
        tool_output = None
        for step in response.get('intermediate_steps', []):
            if isinstance(step, tuple) and len(step) == 2:
                action, observation = step
                if isinstance(observation, list) and observation and isinstance(observation[0], dict):
                    tool_output = observation
                elif isinstance(observation, str) and action.tool in ["google_search_tool", "knowledge_base_tool"]:
                    tool_output = observation
        reply = response.get("output", "I'm not sure how to respond to that.")
        return ChatResponse(response=reply, tool_output=tool_output)

# -------------------- Tools --------------------

@tool
def google_search_tool(query: str, num_results: int = 5) -> List[dict]:
    """Perform a Google web search using serper.dev API (no external SDK). Requires SERPER_API_KEY env var."""
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        return [{"error": "SERPER_API_KEY not set"}]

    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {"q": query}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("organic", [])
        simplified = [
            {
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet"),
            }
            for item in results[:num_results]
        ]
        return simplified
    except Exception as exc:
        return [{"error": str(exc)}]

@tool
def knowledge_base_tool(document_id: int) -> str:
    """Fetch the full content of a document from the knowledge base by its ID."""
    if global_db is None:
        return "No database session available."

    doc = global_db.query(DocumentInDB).filter(DocumentInDB.id == document_id).first()
    if not doc:
        return f"Document with id {document_id} not found."
    return doc.content

def list_groq_models() -> List[str]:
    """Return available models from Groq API."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return []
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        resp = requests.get("https://api.groq.com/openai/models", headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [m["id"] for m in data.get("data", [])]
    except Exception:
        return []