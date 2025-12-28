"""
Google Calendar API integration for continuum.ai

Fetches user availability and events to determine free time slots.
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
from fastapi import HTTPException

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError as e:
    # ImportError will be caught when functions are called
    pass


class CalendarEvent(BaseModel):
    """Represents a calendar event."""
    id: str
    summary: str
    start: str  # ISO format datetime
    end: str    # ISO format datetime
    description: str | None = None
    location: str | None = None
    attendees: list[str] = []
    busy: bool = True  # True if this blocks time


class FreeSlot(BaseModel):
    """Represents a free time slot."""
    start: str  # ISO format datetime
    end: str    # ISO format datetime
    duration_minutes: int


class CalendarAvailability(BaseModel):
    """User's calendar availability for a time period."""
    start_date: str
    end_date: str
    events: list[CalendarEvent]
    free_slots: list[FreeSlot]
    busy_hours: int
    free_hours: float


def _get_credentials():
    """
    Get Google Calendar credentials.
    
    For development, use service account or OAuth.
    For production, use service account key file.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="Google Calendar API libraries not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )
    
    # Try service account first (production)
    service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    # Also check if token.json is a service account
    token_file = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
    
    # Check if token.json is a service account
    if os.path.exists(token_file):
        try:
            import json
            with open(token_file, 'r') as f:
                token_data = json.load(f)
                if token_data.get('type') == 'service_account':
                    # It's a service account
                    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
                    credentials = service_account.Credentials.from_service_account_file(
                        token_file, scopes=SCOPES
                    )
                    return credentials
        except:
            pass
    
    # Use explicit service account file if provided
    if service_account_file and os.path.exists(service_account_file):
        SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file, scopes=SCOPES
        )
        return credentials
    
    # Try OAuth token file (development)
    creds = None
    
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, 
            ['https://www.googleapis.com/auth/calendar.readonly'])
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise HTTPException(
                status_code=401,
                detail="Google Calendar credentials not found. "
                       "Set GOOGLE_SERVICE_ACCOUNT_FILE or run OAuth flow."
            )
    
    return creds


async def list_calendars() -> list[dict]:
    """
    List all accessible calendars.
    
    Returns:
        List of calendars with id, summary, and description.
    """
    try:
        from googleapiclient.discovery import build
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="Google Calendar API libraries not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )
    
    try:
        creds = _get_credentials()
        service = build('calendar', 'v3', credentials=creds)
        
        # Try to list calendars
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])
        
        # If empty, it might be a service account (needs calendar sharing)
        if not calendars:
            try:
                # Try to get primary calendar directly (might work if using OAuth)
                primary_cal = service.calendars().get(calendarId='primary').execute()
                calendars = [{
                    'id': primary_cal.get('id', 'primary'),
                    'summary': primary_cal.get('summary', 'Primary Calendar'),
                    'description': primary_cal.get('description'),
                    'primary': True
                }]
            except HttpError:
                # Service accounts return empty calendarList until calendars are shared
                # Return empty list with helpful message in description
                return [{
                    "id": "primary",
                    "summary": "No calendars found",
                    "description": "Service account detected. Share your calendar with the service account email (check token.json for 'client_email')",
                    "primary": False
                }]
        
        return [
            {
                "id": cal.get('id'),
                "summary": cal.get('summary'),
                "description": cal.get('description'),
                "primary": cal.get('primary', False)
            }
            for cal in calendars
        ]
    except HttpError as e:
        raise HTTPException(
            status_code=e.resp.status,
            detail=f"Google Calendar API error: {e}. Details: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error listing calendars: {str(e)}"
        )


def _is_service_account() -> bool:
    """
    Check if we're using a service account (not OAuth).
    Service accounts need to use email addresses as calendar IDs for shared calendars.
    """
    service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    token_file = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
    
    # Check explicit service account file
    if service_account_file and os.path.exists(service_account_file):
        return True
    
    # Check if token.json is a service account
    if os.path.exists(token_file):
        try:
            import json
            with open(token_file, 'r') as f:
                token_data = json.load(f)
                return token_data.get('type') == 'service_account'
        except:
            pass
    
    return False


def _normalize_calendar_id(calendar_id: str, user_email: Optional[str] = None) -> str:
    """
    Normalize calendar ID.
    
    For OAuth: Convert email to 'primary' for user's own calendar.
    For Service Accounts: Keep email addresses as-is (needed for shared calendars).
    """
    # If it's already "primary", use it
    if calendar_id == "primary":
        return calendar_id
    
    # For service accounts, preserve email addresses (needed for shared calendars)
    if _is_service_account():
        return calendar_id
    
    # For OAuth, convert email to "primary" if it's the user's own email
    if user_email and calendar_id == user_email:
        return "primary"
    
    # Otherwise, use as-is
    return calendar_id


async def get_events(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    calendar_id: str = "primary"
) -> list[CalendarEvent]:
    """
    Fetch calendar events for a date range.
    
    Args:
        start_date: ISO format date string (default: today)
        end_date: ISO format date string (default: 7 days from start)
        calendar_id: Calendar ID (default: "primary")
    
    Returns:
        List of calendar events
    """
    try:
        from googleapiclient.discovery import build
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="Google Calendar API libraries not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )
    
    try:
        creds = _get_credentials()
        service = build('calendar', 'v3', credentials=creds)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build Calendar service: {str(e)}"
        )
    
    # For service accounts, preserve email addresses (needed for shared calendars)
    # For OAuth, convert email to "primary"
    if '@' in calendar_id and not _is_service_account():
        calendar_id = "primary"
    
    # Default to this week
    if not start_date:
        start_date = datetime.now().isoformat() + 'Z'
    else:
        # Ensure timezone if not provided
        if not start_date.endswith('Z') and '+' not in start_date:
            start_date += 'T00:00:00Z'
    
    if not end_date:
        end_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00')) + timedelta(days=7)
        end_date = end_dt.isoformat().replace('+00:00', 'Z')
    else:
        if not end_date.endswith('Z') and '+' not in end_date:
            end_date += 'T23:59:59Z'
    
    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_date,
            timeMax=end_date,
            maxResults=100,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        result = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            attendees = [attendee.get('email', '') 
                        for attendee in event.get('attendees', [])]
            
            result.append(CalendarEvent(
                id=event['id'],
                summary=event.get('summary', 'No Title'),
                start=start,
                end=end,
                description=event.get('description'),
                location=event.get('location'),
                attendees=attendees,
                busy=True
            ))
        
        return result
        
    except HttpError as e:
        if e.resp.status == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Calendar '{calendar_id}' not found. Try using 'primary' for your main calendar, or use list_calendars() to see available calendars."
            )
        raise HTTPException(
            status_code=e.resp.status,
            detail=f"Google Calendar API error: {e}"
        )


def _calculate_free_slots(
    events: list[CalendarEvent],
    start_date: str,
    end_date: str,
    work_hours_start: int = 9,
    work_hours_end: int = 17
) -> list[FreeSlot]:
    """
    Calculate free time slots between events.
    
    Args:
        events: List of calendar events
        start_date: Start of period (ISO format)
        end_date: End of period (ISO format)
        work_hours_start: Start of workday (0-23)
        work_hours_end: End of workday (0-23)
    
    Returns:
        List of free time slots
    """
    from datetime import timezone
    
    # Parse dates
    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    
    # Convert to UTC if needed
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
    
    # Sort events by start time
    sorted_events = sorted(events, key=lambda e: e.start)
    
    free_slots = []
    current_time = start_dt
    
    for event in sorted_events:
        event_start = datetime.fromisoformat(event.start.replace('Z', '+00:00'))
        if event_start.tzinfo is None:
            event_start = event_start.replace(tzinfo=timezone.utc)
        
        # Only consider work hours
        if current_time.hour < work_hours_start:
            current_time = current_time.replace(hour=work_hours_start, minute=0, second=0)
        
        if event_start.hour > work_hours_end:
            event_start = event_start.replace(hour=work_hours_end, minute=0, second=0)
        
        # If there's a gap before this event, it's free time
        if current_time < event_start:
            gap_minutes = (event_start - current_time).total_seconds() / 60
            if gap_minutes >= 15:  # Only slots >= 15 minutes
                free_slots.append(FreeSlot(
                    start=current_time.isoformat(),
                    end=event_start.isoformat(),
                    duration_minutes=int(gap_minutes)
                ))
        
        # Move current_time to end of this event
        event_end = datetime.fromisoformat(event.end.replace('Z', '+00:00'))
        if event_end.tzinfo is None:
            event_end = event_end.replace(tzinfo=timezone.utc)
        current_time = max(current_time, event_end)
    
    # Check if there's free time after the last event
    if current_time < end_dt:
        if current_time.hour < work_hours_end:
            if end_dt.hour > work_hours_end:
                end_dt = end_dt.replace(hour=work_hours_end, minute=0, second=0)
            
            gap_minutes = (end_dt - current_time).total_seconds() / 60
            if gap_minutes >= 15:
                free_slots.append(FreeSlot(
                    start=current_time.isoformat(),
                    end=end_dt.isoformat(),
                    duration_minutes=int(gap_minutes)
                ))
    
    return free_slots


async def get_availability(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    calendar_id: str = "primary",
    work_hours_start: int = 9,
    work_hours_end: int = 17
) -> CalendarAvailability:
    """
    Get user's calendar availability including free slots.
    
    Args:
        start_date: Start date (ISO format, default: today)
        end_date: End date (ISO format, default: 7 days from start)
        calendar_id: Calendar ID (default: "primary")
        work_hours_start: Start of workday hour (0-23)
        work_hours_end: End of workday hour (0-23)
    
    Returns:
        CalendarAvailability with events and free slots
    """
    # Default to this week
    if not start_date:
        now = datetime.now()
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
    
    if not end_date:
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_date = (start_dt + timedelta(days=7)).isoformat().replace('+00:00', 'Z')
    
    # For service accounts, preserve email addresses (needed for shared calendars)
    # For OAuth, convert email to "primary"
    if '@' in calendar_id and not _is_service_account():
        calendar_id = "primary"
    
    # Fetch events
    events = await get_events(start_date, end_date, calendar_id)
    
    # Calculate free slots
    free_slots = _calculate_free_slots(events, start_date, end_date, work_hours_start, work_hours_end)
    
    # Calculate total busy/free hours
    total_busy_minutes = sum(
        (datetime.fromisoformat(e.end.replace('Z', '+00:00')) - 
         datetime.fromisoformat(e.start.replace('Z', '+00:00'))).total_seconds() / 60
        for e in events
    )
    total_busy_hours = total_busy_minutes / 60
    
    total_free_minutes = sum(slot.duration_minutes for slot in free_slots)
    total_free_hours = total_free_minutes / 60
    
    return CalendarAvailability(
        start_date=start_date,
        end_date=end_date,
        events=events,
        free_slots=free_slots,
        busy_hours=round(total_busy_hours, 1),
        free_hours=round(total_free_hours, 1)
    )


async def get_today_events(calendar_id: str = "primary") -> list[CalendarEvent]:
    """Get all events for today."""
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    return await get_events(
        start_date=today_start.isoformat() + 'Z',
        end_date=today_end.isoformat() + 'Z',
        calendar_id=calendar_id
    )


async def get_this_week_availability(
    calendar_id: str = "primary",
    work_hours_start: int = 9,
    work_hours_end: int = 17
) -> CalendarAvailability:
    """Get availability for the current week (today + 7 days)."""
    return await get_availability(
        calendar_id=calendar_id,
        work_hours_start=work_hours_start,
        work_hours_end=work_hours_end
    )

