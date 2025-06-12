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

load_dotenv()

global_db = None
global_roadmap_id = None

@tool
def find_tickets_tool(departure_id: str, destination_id: str, start_date: str, end_date: str) -> Any:
    """Find tickets for a given departure and destination and dates and saves them to the database. departure_id and destination_id are IATA codes. start_date and end_date are dates in the format YYYY-MM-DD"""
    return find_tickets(global_db, global_roadmap_id, departure_id, destination_id, start_date, end_date)


@tool
def find_activities_tool(destination: str, interests: list) -> str:
    """Find activities for a given destination and list of interests. Logs to terminal when called."""
    print(f"[TOOL] find_activities_tool called with: roadmap_id={global_roadmap_id}, destination={destination}, interests={interests}")
    return f"Activities found in {destination} for interests: {', '.join(interests)}."

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    roadmap_id: int

class ChatResponse(BaseModel):
    response: str
    tool_output: Optional[Any] = None

class AIAgent:
    def __init__(self):
        self.llm = ChatGroq(
            model="meta-llama/llama-4-maverick-17b-128e-instruct",
            temperature=0.7,
            groq_api_key=os.environ.get("GROQ_API_KEY"),
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a friendly and helpful travel planning assistant.\nYour goal is to help the user plan a trip by gathering their preferences step-by-step.\n\nAs soon as you have all the information needed for a planning step (like travel dates, hotel preferences, or interests), IMMEDIATELY use the appropriate tool. Do not wait for further user input if you can proceed.\n\nAfter using a tool, confirm with the user and ask for the next missing piece of information.\n\nIf you do not have enough information for a tool, ask the user a clear, specific question to get it.\n\nAlways be friendly and conversational.\n\nExample:\nUser: I want to go to Paris from July 10 to July 15.\nThought: I have the destination and dates. I should find tickets.\nAction: find_tickets_tool(destination='Paris', start_date='2024-07-10', end_date='2024-07-15')\nObservation: Tickets found for Paris from 2024-07-10 to 2024-07-15.\nFinal Answer: I found tickets for Paris from July 10 to July 15! Would you like to look for hotels next?\n\nBased on the user's request, you can:\n1.  Ask for clarifying information if you don't have enough details (e.g., travel dates, hotel preferences, interests).\n2.  Use the available tools if you have all the necessary information for a planning step.\n\nAfter a tool is used successfully, confirm with the user and ask what they'd like to do next. YOU HAVE TO USE TOOLS IF IT IS NEEDED (WHEN SEARCHING FOR TICKETS/HOTLES/FOOD/ACTIVITY). YOU SHOULD CALL 1 TOOL AT A MESSAGE"""),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])

    async def chat(self, request: ChatRequest, db: Session) -> ChatResponse:
        global global_db, global_roadmap_id
        global_db = db
        global_roadmap_id = request.roadmap_id
        tools = [find_tickets_tool, find_hotels_tool, find_activities_tool]
        agent = create_tool_calling_agent(self.llm, tools, self.prompt)
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True, return_intermediate_steps=True)
        chat_history = []
        for msg in request.messages[:-1]:
            chat_history.append(HumanMessage(content=msg.content) if msg.role == "user" else AIMessage(content=msg.content))
        user_input = request.messages[-1].content
        response = await agent_executor.ainvoke({
            "input": user_input,
            "chat_history": chat_history,
        })
        tool_output = None
        for step in response.get('intermediate_steps', []):
            if isinstance(step, tuple) and len(step) == 2:
                action, observation = step
                if isinstance(observation, list) and observation and isinstance(observation[0], dict):
                    tool_output = observation
                elif isinstance(observation, str) and action.tool in ["find_tickets_tool", "find_hotels_tool", "find_activities_tool"]:
                    tool_output = observation
        reply = response.get("output", "I'm not sure how to respond to that.")
        # If tool_output contains segments with both outbound and return, prepend a summary
        if tool_output and isinstance(tool_output, list) and any('segments' in f for f in tool_output):
            has_outbound = any(any(seg.get('direction') == 'outbound' for seg in f['segments']) for f in tool_output)
            has_return = any(any(seg.get('direction') == 'return' for seg in f['segments']) for f in tool_output)
            if has_outbound and has_return:
                reply = 'Here are your outbound and return flight options. ' + reply
        return ChatResponse(response=reply, tool_output=tool_output)