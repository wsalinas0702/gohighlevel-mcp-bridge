import os
from dotenv import load_dotenv
import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone

# Load environment variables from .env (for local development)
load_dotenv()

# Read required config from environment
GHL_API_KEY = os.getenv("GHL_API_KEY")
GHL_LOCATION_ID = os.getenv("GHL_LOCATION_ID")
GHL_CALENDAR_ID = os.getenv("GHL_CALENDAR_ID")  # optional default calendar for appointments
GHL_API_BASE = os.getenv("GHL_API_BASE", "https://services.leadconnectorhq.com")

if not GHL_API_KEY or not GHL_LOCATION_ID:
    raise RuntimeError("Environment variables GHL_API_KEY and GHL_LOCATION_ID must be set with your credentials.")

# Common headers for GoHighLevel API requests (using Private Integration Token auth and API version)
COMMON_HEADERS = {
    "Authorization": f"Bearer {GHL_API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Version": "2021-07-28"  # using latest API version date
}

app = FastAPI(title="GoHighLevel MCP Bridge", description="FastAPI bridge to GoHighLevel API (MCP server)", version="1.0.0")

# Serve the OpenAI Agent manifest at the standard path
@app.get("/.well-known/ai-plugin.json", include_in_schema=False)
async def serve_manifest(request: Request):
    """Return the plugin manifest JSON."""
    base_url = request.url.scheme + "://" + request.headers.get("host")
    manifest = {
        "schema_version": "v1",
        "name_for_human": "GoHighLevel MCP Bridge",
        "name_for_model": "gohighlevel_mcp",
        "description_for_human": "Bridge to connect an OpenAI Agent with GoHighLevel (CRM) sub-account features.",
        "description_for_model": "Tools to create/update contacts, send emails/SMS, manage opportunities, and schedule appointments via GoHighLevel API.",
        "auth": {"type": "none"},
        "api": {
            "type": "openapi",
            "url": f"{base_url}/openapi.json",
            "is_user_authenticated": False
        },
        "logo_url": "https://example.com/logo.png",
        "contact_email": "support@example.com",
        "legal_info_url": "https://example.com/terms"
    }
    return JSONResponse(manifest)

def forward_to_ghl(method: str, endpoint: str, data: dict = None, params: dict = None):
    """
    Helper function to forward an HTTP request to the GoHighLevel API and return the response.
    """
    url = f"{GHL_API_BASE}{endpoint}"
    try:
        response = requests.request(method, url, headers=COMMON_HEADERS, json=data, params=params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Request to GoHighLevel failed: {e}")
    # Parse JSON if possible, otherwise return text
    try:
        result = response.json()
    except ValueError:
        result = {"message": response.text or "No response body"}
    return JSONResponse(status_code=response.status_code, content=result)

# Pydantic models for request bodies
class ContactCreate(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

class ContactUpdate(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

class SMSRequest(BaseModel):
    contactId: str
    message: str

class EmailRequest(BaseModel):
    contactId: str
    subject: str
    body: str

class OpportunityCreate(BaseModel):
    name: str
    contactId: str
    pipelineId: str
    pipelineStageId: str
    status: str = "open"

class OpportunityUpdate(BaseModel):
    name: Optional[str] = None
    pipelineId: Optional[str] = None
    pipelineStageId: Optional[str] = None
    status: Optional[str] = None

class AppointmentCreate(BaseModel):
    contactId: str
    startTime: str  # ISO 8601 datetime string
    calendarId: Optional[str] = None

@app.post("/contacts", summary="Create a new contact")
def create_contact(contact: ContactCreate):
    """Create a new contact in the GoHighLevel sub-account."""
    data = contact.dict()
    data["locationId"] = GHL_LOCATION_ID  # include sub-account ID in request
    return forward_to_ghl("POST", "/contacts/", data=data)

@app.put("/contacts/{contact_id}", summary="Update an existing contact")
def update_contact(contact_id: str, contact: ContactUpdate):
    """Update an existing contact's information."""
    data = contact.dict(exclude_none=True)
    if data:
        data["locationId"] = GHL_LOCATION_ID
    return forward_to_ghl("PUT", f"/contacts/{contact_id}", data=data)

@app.post("/send_sms", summary="Send an SMS to a contact")
def send_sms(request: SMSRequest):
    """Send an SMS message to a contact's primary phone number."""
    payload = {
        "contactId": request.contactId,
        "body": request.message
    }
    # This calls the Conversations API to send an outbound SMS
    return forward_to_ghl("POST", "/conversations/messages", data=payload)

@app.post("/send_email", summary="Send an Email to a contact")
def send_email(request: EmailRequest):
    """Send an email to a contact's primary email address."""
    payload = {
        "contactId": request.contactId,
        "subject": request.subject,
        "body": request.body
    }
    # Uses the account's configured email service to send the email to the contact
    return forward_to_ghl("POST", "/conversations/messages", data=payload)

@app.get("/pipelines", summary="Get available pipelines and stages")
def get_pipelines():
    """Retrieve all pipelines and their stages (for opportunities)."""
    return forward_to_ghl("GET", "/opportunities/pipelines")

@app.post("/opportunities", summary="Create a new opportunity (deal)")
def create_opportunity(opportunity: OpportunityCreate):
    """Create a sales opportunity in a specific pipeline and stage."""
    data = opportunity.dict()
    data["locationId"] = GHL_LOCATION_ID
    return forward_to_ghl("POST", "/opportunities/", data=data)

@app.put("/opportunities/{opportunity_id}", summary="Update an existing opportunity")
def update_opportunity(opportunity_id: str, updates: OpportunityUpdate):
    """Update fields of an existing opportunity (e.g. move stage, change status)."""
    data = updates.dict(exclude_none=True)
    if data:
        data["locationId"] = GHL_LOCATION_ID
    return forward_to_ghl("PUT", f"/opportunities/{opportunity_id}", data=data)

@app.post("/add_to_campaign", summary="Add contact to a campaign")
def add_to_campaign(contactId: str, campaignId: str):
    """Trigger a campaign by adding a contact to the specified campaign."""
    return forward_to_ghl("POST", f"/contacts/{contactId}/campaigns/{campaignId}")

@app.post("/add_to_workflow", summary="Add contact to a workflow")
def add_to_workflow(contactId: str, workflowId: str):
    """Trigger a workflow by adding a contact to the specified workflow."""
    return forward_to_ghl("POST", f"/contacts/{contactId}/workflow/{workflowId}")

@app.post("/appointments", summary="Schedule a new appointment")
def schedule_appointment(appt: AppointmentCreate):
    """Schedule an appointment on a calendar for a contact."""
    data = appt.dict()
    # Use default calendar from env if not provided in request
    if not data.get("calendarId"):
        if not GHL_CALENDAR_ID:
            raise HTTPException(status_code=400, detail="calendarId is required (no default set).")
        data["calendarId"] = GHL_CALENDAR_ID
    data["locationId"] = GHL_LOCATION_ID
    return forward_to_ghl("POST", "/calendars/events/appointments", data=data)

@app.get("/appointments", summary="List appointments in a date range")
def list_appointments(calendarId: Optional[str] = None, startTime: Optional[str] = None, endTime: Optional[str] = None):
    """List calendar appointments within a specified date range (defaults to next 7 days)."""
    # Determine calendarId to use
    if not calendarId:
        if GHL_CALENDAR_ID:
            calendarId = GHL_CALENDAR_ID
        else:
            raise HTTPException(status_code=400, detail="calendarId is required (no default set).")
    # Default date range: now to now+7 days
    if not startTime:
        start = datetime.now(timezone.utc)
        startTime = start.isoformat()
    if not endTime:
        end = datetime.now(timezone.utc) + timedelta(days=7)
        endTime = end.isoformat()
    params = {"calendarId": calendarId, "startTime": startTime, "endTime": endTime}
    return forward_to_ghl("GET", "/calendars/events", params=params)
