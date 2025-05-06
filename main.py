from fastapi import Path

@app.post("/review-ticket/{ticket_id}")
def review_ticket(
    ticket_id: int = Path(..., description="Zendesk Ticket ID to review"),
    agent_email: str = Query("eirik.strand@nshift.com")
):
    # Fetch the ticket from Zendesk
    url = f"{ZENDESK_DOMAIN}/api/v2/tickets/{ticket_id}.json"
    response = requests.get(url, auth=auth)
    if response.status_code != 200:
        return {"error": f"Failed to fetch ticket {ticket_id}: {response.text}"}

    ticket_data = response.json().get("ticket", {})

    # Build the review payload (using default evaluation structure)
    review_payload = {
        "ticket_id": ticket_id,
        "agent_email": agent_email,
        "evaluation": {
            "Professional Language/Tone used": "Yes",
            "Correct ticket categorization used": "Yes",
            "Correct ticket status used": "Yes",
            "Correct ticket priority used": "Yes",
            "Verified if customer had any other tickets related to the same case": "No",
            "Captured all relevant details in the ticket": "Yes",
            "Ensured a proper understanding of the customer's request": "Yes",
            "Owning the conversation and the actions": "Yes",
            "Followed proper procedure to resolve the ticket": "Yes",
            "Phone follow-up utilized to speed up the process": "No",
            "Provided timely assistance": "Yes",
            "Confirmed the resolution with the customer": "Yes",
            "Where applicable, correct invoicing process was used": "N/A",
            "Displayed satisfactory technical competence in handling the ticket": "Yes"
        },
        "score": "88%",
        "comments_for_improvement": {
            "strengths": (
                f"{agent_email} responded quickly and professionally, "
                "immediately acknowledged the issue, and provided detailed logs or escalations where needed. "
                "Tone remained professional and helpful."
            ),
            "suggestions": [
                "Check for related tickets to consolidate context.",
                "Use a phone follow-up to speed up coordination in urgent cases."
            ]
        }
    }

    # Send to Azure Logic App
    headers = {'Content-Type': 'application/json'}
    try:
        logic_response = requests.post(
            AZURE_LOGIC_APP_URL,
            headers=headers,
            data=json.dumps(review_payload)
        )
        return {
            "sent_payload": review_payload,
            "logic_app_status": logic_response.status_code,
            "logic_app_response": logic_response.json() if logic_response.headers.get("Content-Type", "").startswith("application/json") else logic_response.text
        }
    except Exception as e:
        return {"error": str(e)}
