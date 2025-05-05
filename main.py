from fastapi import FastAPI, Query
import requests, os

app = FastAPI()

ZENDESK_DOMAIN = "https://nshift.zendesk.com"
EMAIL = os.getenv("EMAIL")
API_TOKEN = os.getenv("API_TOKEN")
auth = (f"{EMAIL}/token", API_TOKEN)

@app.get("/")
def home():
    return {"message": "✅ Zendesk GPT Bridge is live. Try /tickets, /search, or /summarize."}

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
