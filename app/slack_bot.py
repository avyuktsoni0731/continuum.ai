"""
Slack bot for continuum.ai

Handles Slack events and uses the conversational agent to respond.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional

# Set up logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
    logger.info(f"Loaded .env from: {env_path}")
else:
    # Try loading from current directory as fallback
    load_dotenv()
    logger.warning(f".env not found at {env_path}, trying current directory")

# Verify critical env vars are loaded
slack_token = os.getenv("SLACK_BOT_TOKEN")
if slack_token:
    logger.info(f"SLACK_BOT_TOKEN found (length: {len(slack_token)})")
else:
    logger.error("SLACK_BOT_TOKEN not found in environment!")

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
            logger.info("Initializing ConversationalAgent...")
            agent = ConversationalAgent()
            logger.info("ConversationalAgent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}", exc_info=True)
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
    
    logger.info(f"Posting to Slack channel {channel}: {text[:100]}...")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        result = response.json()
        
        # Check if Slack API returned an error (even with 200 status)
        if not result.get("ok"):
            error = result.get("error", "unknown_error")
            logger.error(f"Slack API error: {error} - {result}")
            raise Exception(f"Slack API error: {error}")
        
        logger.info(f"Successfully posted to Slack: {result.get('ts')}")
        return result


@app.post("/slack/events")
async def slack_events(request: Request):
    """
    Handle Slack events (URL verification, message events, etc.)
    """
    data = await request.json()
    logger.info(f"Received Slack event: {data.get('type')}")
    
    # URL verification challenge
    if data.get("type") == "url_verification":
        challenge = data.get("challenge")
        logger.info(f"URL verification challenge: {challenge}")
        return JSONResponse(content={"challenge": challenge})
    
    # Event handling
    if data.get("type") == "event_callback":
        event = data.get("event", {})
        event_type = event.get("type")
        logger.info(f"Event type: {event_type}, Channel: {event.get('channel')}")
        
        # Ignore bot messages
        if event.get("bot_id"):
            logger.info("Ignoring bot message")
            return JSONResponse(content={"status": "ok"})
        
        # Handle app mentions and direct messages
        if event_type == "app_mention" or event_type == "message":
            # Skip if in a thread (to avoid loops)
            if event.get("thread_ts"):
                logger.info("Ignoring threaded message")
                return JSONResponse(content={"status": "ok"})
            
            channel = event.get("channel")
            user_message = event.get("text", "").strip()
            logger.info(f"User message: {user_message}")
            
            # Get bot user ID from event (if available)
            bot_id = event.get("bot_id") or data.get("authorizations", [{}])[0].get("user_id")
            
            # Remove bot mention if present (format: <@U123456>)
            import re
            if bot_id:
                user_message = re.sub(rf"<@{bot_id}>", "", user_message).strip()
            # Also remove generic mentions
            user_message = re.sub(r"<@[A-Z0-9]+>", "", user_message).strip()
            
            if not user_message:
                logger.info("Empty message after cleaning")
                return JSONResponse(content={"status": "ok"})
            
            # Process with agent
            try:
                logger.info(f"Processing message with agent: {user_message}")
                agent_instance = get_agent()
                response = await agent_instance.chat(user_message)
                logger.info(f"Agent response: {response[:100]}...")
                
                # Post response to Slack
                await post_to_slack(channel, response, thread_ts=event.get("ts"))
                logger.info("Successfully processed and posted response")
                
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                error_msg = f"Sorry, I encountered an error: {str(e)}"
                try:
                    await post_to_slack(channel, error_msg, thread_ts=event.get("ts"))
                except Exception as post_error:
                    logger.error(f"Failed to post error message: {post_error}", exc_info=True)
    
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


@app.get("/test-slack")
async def test_slack():
    """Test endpoint to verify Slack token and posting."""
    import os
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        return {"error": "SLACK_BOT_TOKEN not set"}
    
    # Test posting to a test channel (you'll need to set TEST_CHANNEL_ID in .env)
    test_channel = os.getenv("SLACK_TEST_CHANNEL_ID", "C1234567890")  # Replace with your channel ID
    
    try:
        await post_to_slack(test_channel, "Test message from continuum.ai bot!")
        return {"status": "success", "message": "Test message sent"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)

