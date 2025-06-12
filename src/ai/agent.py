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
import http.client
import json

load_dotenv()

SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

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
            ("system", """You are a helpful AI assistant.\n\nYour primary goals:\n1. Answer user questions conversationally.\n2. When the user needs external information, use the available tools:\n   • google_search_tool — query the web and return concise search results.\n   • knowledge_base_tool — fetch full text of stored documents the user references.\n\nIf you need additional context you don't yet have, explicitly ask the user what you need.\nAlways cite information sources when appropriate and keep answers clear and concise.\nCALL AT MOST ONE TOOL PER MESSAGE when needed."""),
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

# -------------------- New Tools --------------------


@tool
def google_search_tool(query: str, num_results: int = 5) -> List[dict]:
    """Perform a Google search using Serper.dev REST API. Requires SERPER_API_KEY env var."""
    api_key = SERPER_API_KEY
    if not api_key:
        return [{"error": "SERPER_API_KEY not set"}]

    try:
        conn = http.client.HTTPSConnection("google.serper.dev")
        payload = json.dumps({"q": query, "num": num_results})
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        conn.request("POST", "/search", payload, headers)
        res = conn.getresponse()
        data = res.read().decode()
        result_json = json.loads(data)
        organic = result_json.get("organic", [])
        simplified = [
            {
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet"),
            }
            for item in organic[:num_results]
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