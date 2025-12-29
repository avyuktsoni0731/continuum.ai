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
        start: Start time in ISO format (e.g., '2026-01-01T10:00:00Z') or date string (e.g., '30-12-2025 10:00')
        end: End time in ISO format (e.g., '2026-01-01T11:00:00Z') or date string (e.g., '30-12-2025 11:00')
        description: Event description (optional)
        location: Event location (optional)
        attendees: List of email addresses to invite (optional)
        calendar_id: Calendar ID or email (default: 'primary'). Can extract email from Slack link format like '<mailto:email@example.com|email@example.com>'
    
    Returns:
        Created event details
    """
    try:
        from googleapiclient.discovery import build
        from app.tools.calendar import _normalize_calendar_id, _get_credentials
        from datetime import datetime
        import re
        from fastapi import HTTPException
    except ImportError:
        return {
            "success": False,
            "error": "Google Calendar API libraries not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        }
    
    try:
        # Extract email from Slack link format if present (e.g., '<mailto:email@example.com|email@example.com>' -> 'email@example.com')
        if calendar_id.startswith('<mailto:') and '|' in calendar_id:
            # Extract email from Slack link format
            match = re.search(r'mailto:([^|>]+)', calendar_id)
            if match:
                calendar_id = match.group(1)
        elif calendar_id.startswith('<') and calendar_id.endswith('>'):
            # Remove angle brackets if present
            calendar_id = calendar_id.strip('<>')
        
        # Parse and normalize date strings if not already in ISO format
        def normalize_datetime(date_str: str) -> str:
            """Convert date string to ISO format."""
            date_str = date_str.strip()
            
            # If already in ISO format, return as-is
            if 'T' in date_str and ('Z' in date_str or '+' in date_str or '-' in date_str[-6:]):
                return date_str
            
            # Try to parse common formats
            formats = [
                '%d-%m-%Y %H:%M',      # 30-12-2025 10:00
                '%d-%m-%Y %H:%M:%S',  # 30-12-2025 10:00:00
                '%Y-%m-%d %H:%M',     # 2025-12-30 10:00
                '%Y-%m-%d %H:%M:%S',  # 2025-12-30 10:00:00
                '%d/%m/%Y %H:%M',     # 30/12/2025 10:00
                '%m/%d/%Y %H:%M',     # 12/30/2025 10:00
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.isoformat() + 'Z'
                except ValueError:
                    continue
            
            # If parsing fails, try to add time if only date provided
            try:
                dt = datetime.strptime(date_str, '%d-%m-%Y')
                return dt.isoformat() + 'Z'
            except ValueError:
                pass
            
            try:
                dt = datetime.strptime(date_str, '%Y-%m-%d')
                return dt.isoformat() + 'Z'
            except ValueError:
                pass
            
            # If all parsing fails, return as-is and let Google Calendar API handle it
            return date_str
        
        # Normalize start and end times
        start = normalize_datetime(start)
        end = normalize_datetime(end)
        
        # Get credentials with write permissions using the existing function
        try:
            creds = _get_credentials(scope='write')
        except HTTPException as e:
            # Handle HTTPException from _get_credentials
            return {
                "success": False,
                "error": f"Google Calendar credentials error: {e.detail}"
            }
        except Exception as cred_error:
            # Handle any other credential errors
            return {
                "success": False,
                "error": f"Google Calendar credentials error: {str(cred_error)}"
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

