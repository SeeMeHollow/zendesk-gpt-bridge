from fastapi import FastAPI, Query, Body
from pydantic import BaseModel, validator
import requests, os, json

app = FastAPI()

ZENDESK_DOMAIN = "https://nshift.zendesk.com"
EMAIL = os.getenv("EMAIL")
API_TOKEN = os.getenv("API_TOKEN")
AZURE_LOGIC_APP_URL = "https://prod-245.westeurope.logic.azure.com:443/workflows/0ebe20fd989b46e0b23fc6316c69c036/triggers/manual/paths/invoke?api-version=2016-06-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=RrHKHz0rgzCTX0Dwb6wFXp6ruVsZUEWc-jTWw8X8TuM"
auth = (f"{EMAIL}/token", API_TOKEN)

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

@app.get("/")
def home():
    return {"message": "✅ Zendesk GPT Bridge is live. Includes ticketing, help center search, and article suggestions."}

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

# Help Center endpoints
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

@app.get("/helpcenter/suggested-articles")
def suggest_articles_for_ticket(query: str = Query(...), locale: str = "en-us"):
    url = f"{ZENDESK_DOMAIN}/api/v2/help_center/{locale}/articles/search.json?query={query}"
    response = requests.get(url, auth=auth)
    if response.status_code != 200:
        return {"error": response.text}
    articles = response.json().get("results", [])
    suggestions = []
    for article in articles[:5]:
        suggestions.append({
            "title": article.get("title"),
            "url": f"https://helpcenter.nshift.com/hc/{locale}/articles/{article.get('id')}",
            "snippet": article.get("body", "")[:300] + "..." if article.get("body") else ""
        })
    return {"suggestions": suggestions}

# Webhook: auto-attach article suggestions to new tickets
@app.post("/webhook/new-ticket")
def new_ticket_listener(payload: dict = Body(...)):
    ticket_id = payload.get("ticket_id")
    subject = payload.get("subject") or ""
    if not ticket_id or not subject:
        return {"error": "Missing ticket_id or subject"}

    # Search Help Center
    suggestions = suggest_articles_for_ticket(query=subject)["suggestions"]
    if not suggestions:
        return {"message": "No article suggestions found."}

    # Prepare internal note
    note = "**Suggested Help Center Articles:**\n\n"
    for a in suggestions:
        note += f"- [{a['title']}]({a['url']})\n"

    comment_payload = {
        "ticket": {
            "comment": {
                "body": note,
                "public": False
            }
        }
    }
    url = f"{ZENDESK_DOMAIN}/api/v2/tickets/{ticket_id}.json"
    response = requests.put(url, auth=auth, json=comment_payload)
    if response.status_code != 200:
        return {"error": response.text}
    return {"message": "Internal note with article suggestions added.", "ticket_id": ticket_id}
