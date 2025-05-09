from fastapi import FastAPI, Query, Body, Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, validator
from starlette.status import HTTP_403_FORBIDDEN
import requests, os, json

app = FastAPI()

# Environment config
ZENDESK_DOMAIN = "https://nshift.zendesk.com"
EMAIL = os.getenv("EMAIL")
API_TOKEN = os.getenv("API_TOKEN")
INTERNAL_SECTION_ID = os.getenv("INTERNAL_GUIDE_SECTION_ID")
AZURE_LOGIC_APP_URL = os.getenv("AZURE_LOGIC_APP_URL")
API_KEY = os.getenv("X_API_KEY")
auth = (f"{EMAIL}/token", API_TOKEN)

# API key security setup
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == API_KEY:
        return api_key_header
    raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid or missing API key")

# Models
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

# Routes
@app.get("/")
def home():
    return {"message": "✅ Zendesk GPT Bridge with Help Center + Internal Guides integrated."}

@app.get("/tickets", dependencies=[Depends(get_api_key)])
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

@app.get("/search", dependencies=[Depends(get_api_key)])
def search_tickets(query: str = Query(...)):
    url = f"{ZENDESK_DOMAIN}/api/v2/search.json?query={query}+type:ticket"
    response = requests.get(url, auth=auth)
    if response.status_code != 200:
        return {"error": response.text}
    results = response.json().get("results", [])
    return {"tickets": [{"id": t["id"], "subject": t["subject"], "status": t["status"]}
                         for t in results if t.get("result_type") == "ticket"]}

@app.get("/summarize", dependencies=[Depends(get_api_key)])
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
    status_count = {}
    for ticket in tickets:
        status = ticket["status"]
        status_count[status] = status_count.get(status, 0) + 1
    return {"summary": f"Total tickets: {len(tickets)}\n" +
                       "\n".join([f"- {k.title()}: {v}" for k, v in status_count.items()])}

@app.get("/ticket/{ticket_id}/comments", dependencies=[Depends(get_api_key)])
def get_ticket_comments(ticket_id: int, message_type: str = Query("all", enum=["all", "public", "internal"])):
    url = f"{ZENDESK_DOMAIN}/api/v2/tickets/{ticket_id}/comments.json"
    response = requests.get(url, auth=auth)
    if response.status_code != 200:
        return {"error": response.text}
    comments = response.json().get("comments", [])
    return {"comments": [{
        "comment_id": c["id"],
        "author_id": c["author_id"],
        "type": "public" if c["public"] else "internal_note",
        "message": c["body"],
        "created_at": c["created_at"]
    } for c in comments if message_type == "all" or (message_type == "public") == c["public"]]}

@app.get("/send-evaluation/template", dependencies=[Depends(get_api_key)])
def get_evaluation_template():
    return EvaluationPayload.schema()["properties"]

@app.post("/send-evaluation", dependencies=[Depends(get_api_key)])
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
            "response": response.json() if "application/json" in response.headers.get("Content-Type", "") else response.text
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/helpcenter/articles", dependencies=[Depends(get_api_key)])
def get_helpcenter_articles(locale: str = "en-us"):
    url = f"{ZENDESK_DOMAIN}/api/v2/help_center/{locale}/articles.json"
    response = requests.get(url, auth=auth)
    return {"articles": response.json().get("articles", [])} if response.ok else {"error": response.text}

@app.get("/helpcenter/article/{article_id}", dependencies=[Depends(get_api_key)])
def get_helpcenter_article(article_id: int):
    url = f"{ZENDESK_DOMAIN}/api/v2/help_center/articles/{article_id}.json"
    response = requests.get(url, auth=auth)
    return {"article": response.json().get("article")} if response.ok else {"error": response.text}

@app.get("/helpcenter/search", dependencies=[Depends(get_api_key)])
def search_helpcenter_articles(query: str, locale: str = "en-us"):
    url = f"{ZENDESK_DOMAIN}/api/v2/help_center/{locale}/articles/search.json?query={query}"
    response = requests.get(url, auth=auth)
    return {"results": response.json().get("results", [])} if response.ok else {"error": response.text}

@app.get("/helpcenter/suggested-articles", dependencies=[Depends(get_api_key)])
def suggest_articles_for_ticket(query: str = Query(...), locale: str = "en-us", include_internal: bool = False):
    articles = []
    if include_internal and INTERNAL_SECTION_ID:
        url_internal = f"{ZENDESK_DOMAIN}/api/v2/help_center/sections/{INTERNAL_SECTION_ID}/articles.json"
        resp = requests.get(url_internal, auth=auth)
        if resp.ok:
            articles.extend(resp.json().get("articles", []))
    url_public = f"{ZENDESK_DOMAIN}/api/v2/help_center/{locale}/articles/search.json?query={query}"
    resp_public = requests.get(url_public, auth=auth)
    if resp_public.ok:
        articles.extend(resp_public.json().get("results", []))
    suggestions = [{
        "title": a.get("title"),
        "url": f"https://helpcenter.nshift.com/hc/{locale}/articles/{a.get('id')}",
        "snippet": a.get("body", "")[:300] + "..." if a.get("body") else ""
    } for a in articles[:5]]
    return {"suggestions": suggestions}

@app.get("/internal-guides/articles", dependencies=[Depends(get_api_key)])
def get_internal_guides(locale: str = "en-us"):
    if not INTERNAL_SECTION_ID:
        return {"error": "Missing INTERNAL_GUIDE_SECTION_ID"}
    url = f"{ZENDESK_DOMAIN}/api/v2/help_center/sections/{INTERNAL_SECTION_ID}/articles.json"
    response = requests.get(url, auth=auth)
    return {"internal_articles": response.json().get("articles", [])} if response.ok else {"error": response.text}

@app.post("/webhook/new-ticket", dependencies=[Depends(get_api_key)])
def new_ticket_listener(payload: dict = Body(...)):
    ticket_id = payload.get("ticket_id")
    subject = payload.get("subject", "")
    if not ticket_id or not subject:
        return {"error": "Missing ticket_id or subject"}
    suggestions = suggest_articles_for_ticket(query=subject, include_internal=True)["suggestions"]
    if not suggestions:
        return {"message": "No article suggestions found."}
    note = "**Suggested Articles (Public + Internal):**\n" + "\n".join(
        [f"- [{a['title']}]({a['url']})" for a in suggestions]
    )
    comment_payload = {"ticket": {"comment": {"body": note, "public": False}}}
    resp = requests.put(f"{ZENDESK_DOMAIN}/api/v2/tickets/{ticket_id}.json", auth=auth, json=comment_payload)
    return {"message": "Internal note added", "ticket_id": ticket_id} if resp.ok else {"error": resp.text}
