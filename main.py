# updated_main.py

from fastapi import FastAPI, HTTPException, Path, Query, Header, Body
from pydantic import BaseModel
from typing import List, Optional
import requests, os

app = FastAPI()

# Constants
ZENDESK_DOMAIN = "https://nshift.zendesk.com"
EMAIL = os.getenv("EMAIL")
API_TOKEN = os.getenv("API_TOKEN")


# Models
class Conversation(BaseModel):
    commentId: int
    user_id: int
    internal_message: bool
    user_type: str
    message: str

class TicketSummary(BaseModel):
    product: str
    title: str
    description: str
    summary: str
    keywords: List[str]

class TicketSummaryResponse(TicketSummary):
    id: int
    created_at: str

class ChatbotReplyCreate(BaseModel):
    ticket_id: int
    product: str
    title: str
    description: str
    response: str
    keywords: str

class ChatbotReplyUpdate(BaseModel):
    product: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    response: Optional[str] = None
    keywords: Optional[str] = None

class ChatbotReply(ChatbotReplyCreate):
    id: int
    created_at: str

# Fake in-memory storage (can be replaced with DB)
summaries = {}
chatbot_replies = {}

# Middleware-like token check
def verify_token(token: str):
    if token != VALID_API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API token")

@app.get("/ticket/{ticketId}/data")
def get_ticket_conversations(ticketId: int, x_api_token: str = Header(...)):
    verify_token(x_api_token)
    ticket_info = {"id": ticketId, "subject": f"Ticket {ticketId}"}
    conversations = [
        Conversation(commentId=1, user_id=123, internal_message=False, user_type="Agent", message="Initial message")
    ]
    return {"ticket_info": ticket_info, "conversations": conversations}

@app.post("/tickets/{ticketId}/summary")
def save_ticket_summary(ticketId: int, summary: TicketSummary, x_api_token: str = Header(...)):
    verify_token(x_api_token)
    if ticketId not in summaries:
        summaries[ticketId] = []
    summary_id = len(summaries[ticketId]) + 1
    summaries[ticketId].append({"id": summary_id, **summary.dict(), "created_at": "2024-01-01T00:00:00Z"})
    return {"message": "Summary saved successfully"}

@app.get("/tickets/{ticketId}/summaries", response_model=List[TicketSummaryResponse])
def get_ticket_summaries(ticketId: int, x_api_token: str = Header(...)):
    verify_token(x_api_token)
    return summaries.get(ticketId, [])

@app.get("/summaries")
def get_all_summaries(x_api_token: str = Header(...)):
    verify_token(x_api_token)
    all_summaries = []
    for tid, items in summaries.items():
        for s in items:
            all_summaries.append({**s, "ticket_id": tid})
    return all_summaries

@app.get("/search/{query}")
def search_tickets(query: str = Path(...), x_api_token: str = Header(...)):
    verify_token(x_api_token)
    url = f"{ZENDESK_DOMAIN}/api/v2/search.json?query={query}+type:ticket"
    response = requests.get(url, auth=auth)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Search failed")
    data = response.json().get("results", [])
    return [
        {"id": d["id"], "subject": d["subject"], "description": d.get("description", "")} for d in data
    ]

@app.post("/chatbot/replies")
def create_reply(payload: ChatbotReplyCreate, x_api_token: str = Header(...)):
    verify_token(x_api_token)
    new_id = len(chatbot_replies) + 1
    chatbot_replies[new_id] = {**payload.dict(), "id": new_id, "created_at": "2024-01-01T00:00:00Z"}
    return {"id": new_id, "message": "Chatbot reply created successfully"}

@app.get("/chatbot/replies")
def get_replies(keywords: Optional[str] = Query(None), x_api_token: str = Header(...)):
    verify_token(x_api_token)
    return list(chatbot_replies.values())

@app.put("/chatbot/replies/{replyId}")
def update_reply(replyId: int, update: ChatbotReplyUpdate, x_api_token: str = Header(...)):
    verify_token(x_api_token)
    if replyId not in chatbot_replies:
        raise HTTPException(status_code=404, detail="Reply not found")
    chatbot_replies[replyId].update({k: v for k, v in update.dict().items() if v is not None})
    return {"message": "Reply updated successfully"}

@app.delete("/chatbot/replies/{replyId}")
def delete_reply(replyId: int, x_api_token: str = Header(...)):
    verify_token(x_api_token)
    if replyId not in chatbot_replies:
        raise HTTPException(status_code=404, detail="Reply not found")
    del chatbot_replies[replyId]
    return {"message": "Reply deleted successfully"}
