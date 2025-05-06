from fastapi import FastAPI, Query, Body
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Union
import requests, os, json

app = FastAPI()

ZENDESK_DOMAIN = "https://nshift.zendesk.com"
EMAIL = os.getenv("EMAIL")
API_TOKEN = os.getenv("API_TOKEN")
AZURE_LOGIC_APP_URL = "https://prod-245.westeurope.logic.azure.com:443/workflows/0ebe20fd989b46e0b23fc6316c69c036/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=RrHKHz0rgzCTX0Dwb6wFXp6ruVsZUEWc-jTWw8X8TuM"
auth = (f"{EMAIL}/token", API_TOKEN)

# Evaluation schema models
class Evaluation(BaseModel):
    Professional_Language_Tone_used: str = Field(..., alias="Professional Language/Tone used")
    Correct_ticket_categorization_used: str = Field(..., alias="Correct ticket categorization used")
    Correct_ticket_status_used: str = Field(..., alias="Correct ticket status used")
    Correct_ticket_priority_used: str = Field(..., alias="Correct ticket priority used")
    Verified_if_customer_had_any_other_tickets_related_to_the_same_case: str = Field(..., alias="Verified if customer had any other tickets related to the same case")
    Captured_all_relevant_details_in_the_ticket: str = Field(..., alias="Captured all relevant details in the ticket")
    Ensured_a_proper_understanding_of_the_customer_request: str = Field(..., alias="Ensured a proper understanding of the customer's request")
    Owning_the_conversation_and_the_actions: str = Field(..., alias="Owning the conversation and the actions")
    Followed_proper_procedure_to_resolve_the_ticket: str = Field(..., alias="Followed proper procedure to resolve the ticket")
    Phone_follow_up_utilized_to_speed_up_the_process: str = Field(..., alias="Phone follow-up utilized to speed up the process")
    Provided_timely_assistance: str = Field(..., alias="Provided timely assistance")
    Confirmed_the_resolution_with_the_customer: str = Field(..., alias="Confirmed the resolution with the customer")
    Where_applicable_correct_invoicing_process_was_used: str = Field(..., alias="Where applicable, correct invoicing process was used")
    Displayed_satisfactory_technical_competence_in_handling_the_ticket: str = Field(..., alias="Displayed satisfactory technical competence in handling the ticket")

    @validator('*')
    def validate_yes_no(cls, v):
        if v not in {"Yes", "No"}:
            raise ValueError("Each field must be 'Yes' or 'No'")
        return v

class EvaluationPayload(BaseModel):
    ticket_id: int
    agent_email: str
    evaluation: Evaluation
    score: str
    comments_for_improvement: Dict[str, Union[str, List[str]]]

@app.get("/")
def home():
    return {
        "message": "✅ Zendesk GPT Bridge is live. Try /tickets, /search, /summarize, /ticket/{ticket_id}/comments, /send-evaluation/template or /send-evaluation."
    }

@app.get("/tickets")
def get_tickets():
    url = f"{ZENDESK_DOMAIN}/api/v2/tickets.json"
    tickets = []
    while url:
        response = requests.get(url, auth=auth)
        if response.status_code != 200:
            return {"error": response.text}
        data = response.json()
        tickets.extend(data.get("tickets", []))
        url = data.get("next_page")
    return {"tickets": tickets}

@app.get("/search")
def search_tickets(query: str = Query(..., description="Search term for tickets")):
    url = f"{ZENDESK_DOMAIN}/api/v2/search.json?query={query}+type:ticket"
    response = requests.get(url, auth=auth)
    if response.status_code != 200:
        return {"error": response.text}
    results = response.json().get("results", [])
    tickets = [
        {"id": t["id"], "subject": t["subject"], "status": t["status"]}
        for t in results if t.get("result_type") == "ticket"
    ]
    return {"tickets": tickets}

@app.get("/summarize")
def summarize_tickets():
    url = f"{ZENDESK_DOMAIN}/api/v2/tickets.json"
    tickets = []
    while url:
        response = requests.get(url, auth=auth)
        if response.status_code != 200:
            return {"error": response.text}
        data = response.json()
        tickets.extend(data.get("tickets", []))
        url = data.get("next_page")
    if not tickets:
        return {"summary": "No tickets found."}
    summary = f"Total tickets: {len(tickets)}\n"
    status_count = {}
    for ticket in tickets:
        status = ticket["status"]
        status_count[status] = status_count.get(status, 0) + 1
    for status, count in status_count.items():
        summary += f"- {status.title()}: {count}\n"
    return {"summary": summary.strip()}

@app.get("/ticket/{ticket_id}/comments")
def get_ticket_comments(ticket_id: int, message_type: str = Query("all", enum=["all", "public", "internal"])):
    url = f"{ZENDESK_DOMAIN}/api/v2/tickets/{ticket_id}/comments.json"
    response = requests.get(url, auth=auth)
    if response.status_code != 200:
        return {"error": response.text}
    comments = response.json().get("comments", [])
    result = []
    for c in comments:
        if message_type == "public" and not c["public"]:
            continue
        if message_type == "internal" and c["public"]:
            continue
        result.append({
            "comment_id": c["id"],
            "author_id": c["author_id"],
            "type": "public" if c["public"] else "internal_note",
            "message": c["body"],
            "created_at": c["created_at"]
        })
    return {"comments": result}

@app.get("/send-evaluation/template")
def get_evaluation_template():
    return {
        "ticket_id": None,
        "agent_email": "",
        "evaluation": {
            "Professional Language/Tone used": "",
            "Correct ticket categorization used": "",
            "Correct ticket status used": "",
            "Correct ticket priority used": "",
            "Verified if customer had any other tickets related to the same case": "",
            "Captured all relevant details in the ticket": "",
            "Ensured a proper understanding of the customer's request": "",
            "Owning the conversation and the actions": "",
            "Followed proper procedure to resolve the ticket": "",
            "Phone follow-up utilized to speed up the process": "",
            "Provided timely assistance": "",
            "Confirmed the resolution with the customer": "",
            "Where applicable, correct invoicing process was used": "",
            "Displayed satisfactory technical competence in handling the ticket": ""
        },
        "score": "",
        "comments_for_improvement": {
            "strengths": "",
            "suggestions": [""]
        }
    }

def send_evaluation(payload: EvaluationPayload):
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(
            AZURE_LOGIC_APP_URL,
            headers=headers,
            json=json.loads(payload.json(by_alias=True))  # Ensures correct dict format
        )
        return {
            "status_code": response.status_code,
            "response": response.json() if response.headers.get("Content-Type", "").startswith("application/json") else response.text
        }
    except Exception as e:
        return {"error": str(e)}
