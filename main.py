from fastapi import FastAPI, Query
from pydantic import BaseModel, validator
import requests, os, json

app = FastAPI()

# Zendesk credentials and base URLs
ZENDESK_DOMAIN = "https://nshift.zendesk.com"
EMAIL = os.getenv("EMAIL")
API_TOKEN = os.getenv("API_TOKEN")
AZURE_LOGIC_APP_URL = "https://prod-245.westeurope.logic.azure.com:443/workflows/0ebe20fd989b46e0b23fc6316c69c036/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=RrHKHz0rgzCTX0Dwb6wFXp6ruVsZUEWc-jTWw8X8TuM"
auth = (f"{EMAIL}/token", API_TOKEN)

# Evaluation models
class Evaluation(BaseModel):
    language_tone: str
    ticket_category: str
    ticket_status: str
    ticket_priority: str
    checked_related_tickets: str
    captured_details: str
    understood_request: str
    owned_actions: str
    followed_procedure: str
    phone_followup: str
    timely_assistance: str
    confirmed_resolution: str
    invoicing_process: str
    technical_competence: str

    @validator('*')
    def validate_yes_no_na(cls, v):
        if v not in {"Yes", "No", "N/A"}:
            raise ValueError("Each field must be 'Yes', 'No', or 'N/A'")
        return v

class EvaluationPayload(Evaluation):
    ticket_id: int
    agent_email: str
    score: str
    strengths: str
    suggestion_1: str
    suggestion_2: str

# General endpoints
@app.get("/")
def home():
    return {"message": "✅ Zendesk GPT Bridge is live. Try /tickets, /search, /summarize, /ticket/{ticket_id}/comments, /helpcenter/articles, /helpcenter/search"}

# Ticket endpoints
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
def search_tickets(query: str = Query(...)):
    url = f"{ZENDESK_DOMAIN}/api/v2/search.json?query={query}+type:ticket"
    response = requests.get(url, auth=auth)
    if response.status_code != 200:
        return {"error": response.text}
    results = response.json().get("results", [])
    tickets = [{"id": t["id"], "subject": t["subject"], "status": t["status"]}
               for t in results if t.get("result_type") == "ticket"]
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

# Evaluation endpoints
@app.get("/send-evaluation/template")
def get_evaluation_template():
    return EvaluationPayload.schema()["properties"]

@app.post("/send-evaluation")
def send_evaluation(payload: EvaluationPayload):
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(
            AZURE_LOGIC_APP_URL,
            headers=headers,
            json=json.loads(payload.json())
        )
        return {
            "status_code": response.status_code,
            "response": response.json() if response.headers.get("Content-Type", "").startswith("application/json") else response.text
        }
    except Exception as e:
        return {"error": str(e)}

# NEW: Help Center integration (Zendesk Guide)
@app.get("/helpcenter/articles")
def get_helpcenter_articles(locale: str = "en-us"):
    url = f"{ZENDESK_DOMAIN}/api/v2/help_center/{locale}/articles.json"
    response = requests.get(url, auth=auth)
    if response.status_code != 200:
        return {"error": response.text}
    return {"articles": response.json().get("articles", [])}

@app.get("/helpcenter/article/{article_id}")
def get_helpcenter_article(article_id: int):
    url = f"{ZENDESK_DOMAIN}/api/v2/help_center/articles/{article_id}.json"
    response = requests.get(url, auth=auth)
    if response.status_code != 200:
        return {"error": response.text}
    return {"article": response.json().get("article")}

@app.get("/helpcenter/search")
def search_helpcenter_articles(query: str, locale: str = "en-us"):
    url = f"{ZENDESK_DOMAIN}/api/v2/help_center/{locale}/articles/search.json?query={query}"
    response = requests.get(url, auth=auth)
    if response.status_code != 200:
        return {"error": response.text}
    return {"results": response.json().get("results", [])}
