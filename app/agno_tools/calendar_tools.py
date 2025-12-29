"""
Agno tool functions for Calendar operations.

Simple functions that wrap existing Calendar functions for Agno.
"""

import logging
from typing import Optional
from app.tools.calendar import (
    list_calendars,
    get_events,
    get_availability,
    get_today_events,
    get_this_week_availability
)

logger = logging.getLogger(__name__)


async def list_calendars_tool() -> dict:
    """List all accessible calendars. Returns calendar id, summary, description, and primary flag."""
    try:
        calendars = await list_calendars()
        return {
            "success": True,
            "count": len(calendars),
            "calendars": calendars
        }
    except Exception as e:
        logger.error(f"Error listing calendars: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def get_calendar_events_tool(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    calendar_id: str = "primary"
) -> dict:
    """Get calendar events for a date range. Use ISO format dates (e.g., '2026-01-01T00:00:00Z'). If dates not provided, defaults to this week."""
    try:
        events = await get_events(start_date=start_date, end_date=end_date, calendar_id=calendar_id)
        return {
            "success": True,
            "count": len(events),
            "events": [event.model_dump() for event in events]
        }
    except Exception as e:
        logger.error(f"Error getting calendar events: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def get_calendar_availability_tool(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    calendar_id: str = "primary",
    work_hours_start: int = 9,
    work_hours_end: int = 17
) -> dict:
    """Get calendar availability including free time slots. Use ISO format dates. Returns events, free slots, busy hours, and free hours."""
    try:
        availability = await get_availability(
            start_date=start_date,
            end_date=end_date,
            calendar_id=calendar_id,
            work_hours_start=work_hours_start,
            work_hours_end=work_hours_end
        )
        return {
            "success": True,
            "availability": availability.model_dump()
        }
    except Exception as e:
        logger.error(f"Error getting calendar availability: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def get_today_events_tool(calendar_id: str = "primary") -> dict:
    """Get all events scheduled for today."""
    try:
        events = await get_today_events(calendar_id=calendar_id)
        return {
            "success": True,
            "count": len(events),
            "events": [event.model_dump() for event in events]
        }
    except Exception as e:
        logger.error(f"Error getting today's events: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def get_this_week_availability_tool(
    calendar_id: str = "primary",
    work_hours_start: int = 9,
    work_hours_end: int = 17
) -> dict:
    """Get availability for the current week (today + 7 days) with free slots."""
    try:
        availability = await get_this_week_availability(
            calendar_id=calendar_id,
            work_hours_start=work_hours_start,
            work_hours_end=work_hours_end
        )
        return {
            "success": True,
            "availability": availability.model_dump()
        }
    except Exception as e:
        logger.error(f"Error getting this week's availability: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


async def create_calendar_event_tool(
    summary: str,
    start: str,
    end: str,
    description: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[list[str]] = None,
    calendar_id: str = "primary"
) -> dict:
    """
    Create a new calendar event.
    
    Args:
        summary: Event title/summary
        start: Start time in ISO format (e.g., '2026-01-01T10:00:00Z')
        end: End time in ISO format (e.g., '2026-01-01T11:00:00Z')
        description: Event description (optional)
        location: Event location (optional)
        attendees: List of email addresses to invite (optional)
        calendar_id: Calendar ID (default: 'primary')
    
    Returns:
        Created event details
    """
    try:
        from googleapiclient.discovery import build
        from app.tools.calendar import _normalize_calendar_id
        from google.oauth2 import service_account
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        import os
        from pathlib import Path
    except ImportError:
        return {
            "success": False,
            "error": "Google Calendar API libraries not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        }
    
    try:
        # Get credentials with write permissions
        creds = None
        service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
        token_file = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
        
        # Resolve paths
        if not os.path.isabs(token_file):
            project_root = Path(__file__).resolve().parent.parent.parent
            token_file = str(project_root / token_file)
            if not os.path.exists(token_file):
                token_file = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
        
        # Try service account first (with write scope)
        if service_account_file:
            if not os.path.isabs(service_account_file):
                project_root = Path(__file__).resolve().parent.parent.parent
                service_account_file = str(project_root / service_account_file)
            if os.path.exists(service_account_file):
                SCOPES = ['https://www.googleapis.com/auth/calendar']
                creds = service_account.Credentials.from_service_account_file(
                    service_account_file, scopes=SCOPES
                )
        
        # Check if token.json is a service account
        if not creds and os.path.exists(token_file):
            try:
                import json
                with open(token_file, 'r') as f:
                    token_data = json.load(f)
                    if token_data.get('type') == 'service_account':
                        SCOPES = ['https://www.googleapis.com/auth/calendar']
                        creds = service_account.Credentials.from_service_account_file(
                            token_file, scopes=SCOPES
                        )
            except:
                pass
        
        # Try OAuth token (with write scope)
        if not creds and os.path.exists(token_file):
            try:
                creds = Credentials.from_authorized_user_file(
                    token_file, 
                    ['https://www.googleapis.com/auth/calendar']
                )
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
            except:
                pass
        
        if not creds or not creds.valid:
            return {
                "success": False,
                "error": "Google Calendar credentials not found or invalid. Set GOOGLE_SERVICE_ACCOUNT_FILE or run OAuth flow with calendar write permissions."
            }
        
        service = build('calendar', 'v3', credentials=creds)
        
        # Normalize calendar ID
        calendar_id = _normalize_calendar_id(calendar_id)
        
        # Build event body
        event_body = {
            'summary': summary,
            'start': {
                'dateTime': start,
                'timeZone': 'UTC'
            },
            'end': {
                'dateTime': end,
                'timeZone': 'UTC'
            }
        }
        
        if description:
            event_body['description'] = description
        
        if location:
            event_body['location'] = location
        
        if attendees:
            event_body['attendees'] = [{'email': email} for email in attendees]
        
        # Create event
        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event_body
        ).execute()
        
        return {
            "success": True,
            "event": {
                "id": created_event.get('id'),
                "summary": created_event.get('summary'),
                "start": created_event['start'].get('dateTime', created_event['start'].get('date')),
                "end": created_event['end'].get('dateTime', created_event['end'].get('date')),
                "description": created_event.get('description'),
                "location": created_event.get('location'),
                "htmlLink": created_event.get('htmlLink'),
                "attendees": [a.get('email') for a in created_event.get('attendees', [])]
            }
        }
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

