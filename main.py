from fastapi import FastAPI
import requests

app = FastAPI()

ZENDESK_DOMAIN = "https://nshift.zendesk.com"
EMAIL = "adrian.norheim@nshift.com"
API_TOKEN = "DjU3ZpYuLhFWKfMTGeei7fxJiamYu3XB5RAIVmG8"

@app.get("/")
def home():
    return {"message": "Zendesk GPT bridge is live. Use /tickets to fetch tickets."}

@app.get("/tickets")
def get_tickets():
    auth = (f"{EMAIL}/token", API_TOKEN)
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