"""
Slack bot for continuum.ai

Handles Slack events and uses the conversational agent to respond.
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import httpx
from app.agent.conversation import ConversationalAgent

app = FastAPI(title="continuum.ai Slack Bot")

# Initialize agent (lazy initialization)
agent: Optional[ConversationalAgent] = None


def get_agent() -> ConversationalAgent:
    """Get or initialize the conversational agent."""
    global agent
    if agent is None:
        try:
            agent = ConversationalAgent()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize agent: {str(e)}"
            )
    return agent


def _get_slack_headers() -> dict:
    """Get Slack API headers."""
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        raise HTTPException(
            status_code=500,
            detail="SLACK_BOT_TOKEN not configured in .env"
        )
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


async def post_to_slack(channel: str, text: str, thread_ts: Optional[str] = None):
    """Post a message to a Slack channel."""
    headers = _get_slack_headers()
    
    payload = {
        "channel": channel,
        "text": text
    }
    
    if thread_ts:
        payload["thread_ts"] = thread_ts
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()


@app.post("/slack/events")
async def slack_events(request: Request):
    """
    Handle Slack events (URL verification, message events, etc.)
    """
    data = await request.json()
    
    # URL verification challenge
    if data.get("type") == "url_verification":
        return JSONResponse(content={"challenge": data.get("challenge")})
    
    # Event handling
    if data.get("type") == "event_callback":
        event = data.get("event", {})
        
        # Ignore bot messages
        if event.get("bot_id"):
            return JSONResponse(content={"status": "ok"})
        
        # Handle app mentions and direct messages
        if event.get("type") == "app_mention" or event.get("type") == "message":
            # Skip if in a thread (to avoid loops)
            if event.get("thread_ts"):
                return JSONResponse(content={"status": "ok"})
            
            channel = event.get("channel")
            user_message = event.get("text", "").strip()
            
            # Get bot user ID from event (if available)
            bot_id = event.get("bot_id") or data.get("authorizations", [{}])[0].get("user_id")
            
            # Remove bot mention if present (format: <@U123456>)
            import re
            if bot_id:
                user_message = re.sub(rf"<@{bot_id}>", "", user_message).strip()
            # Also remove generic mentions
            user_message = re.sub(r"<@[A-Z0-9]+>", "", user_message).strip()
            
            if not user_message:
                return JSONResponse(content={"status": "ok"})
            
            # Process with agent
            try:
                agent_instance = get_agent()
                response = await agent_instance.chat(user_message)
                
                # Post response to Slack
                await post_to_slack(channel, response, thread_ts=event.get("ts"))
                
            except Exception as e:
                error_msg = f"Sorry, I encountered an error: {str(e)}"
                try:
                    await post_to_slack(channel, error_msg, thread_ts=event.get("ts"))
                except:
                    pass  # Fail silently if we can't post error
    
    return JSONResponse(content={"status": "ok"})


@app.post("/slack/commands")
async def slack_commands(request: Request):
    """
    Handle Slack slash commands (e.g., /continuum)
    """
    form_data = await request.form()
    user_message = form_data.get("text", "").strip()
    channel_id = form_data.get("channel_id")
    user_id = form_data.get("user_id")
    
    if not user_message:
        return JSONResponse(content={
            "response_type": "ephemeral",
            "text": "Usage: /continuum <your question>\nExample: /continuum show me open PRs"
        })
    
    try:
        # Process with agent
        agent_instance = get_agent()
        response = await agent_instance.chat(user_message)
        
        return JSONResponse(content={
            "response_type": "in_channel",
            "text": response
        })
    except Exception as e:
        return JSONResponse(content={
            "response_type": "ephemeral",
            "text": f"Error: {str(e)}"
        })


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "continuum.ai-slack-bot"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)

