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
from contextlib import asynccontextmanager
import httpx
from app.agent.conversation import ConversationalAgent
from app.agno_agent import AgnoAgent, should_use_agno


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    try:
        import asyncio
        from app.triggers.scheduler import start_scheduler
        
        # Start scheduler in background task
        async def _run_scheduler():
            await asyncio.sleep(1)  # Small delay to ensure app is fully started
            start_scheduler()
        
        asyncio.create_task(_run_scheduler())
        logger.info("Trigger system scheduler starting...")
    except Exception as e:
        logger.warning(f"Could not start trigger scheduler: {e}")
    
    yield
    
    # Shutdown
    try:
        from app.triggers.scheduler import stop_scheduler
        stop_scheduler()
        logger.info("Trigger system scheduler stopped")
    except Exception as e:
        logger.warning(f"Error stopping trigger scheduler: {e}")


app = FastAPI(title="continuum.ai Slack Bot", lifespan=lifespan)

# Initialize agents (lazy initialization)
agent: Optional[ConversationalAgent] = None
agno_agent: Optional[AgnoAgent] = None

# Event deduplication: track processed events
processed_events = set()


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


def get_agno_agent() -> AgnoAgent:
    """Get or initialize the Agno agent."""
    global agno_agent
    if agno_agent is None:
        try:
            logger.info("Initializing AgnoAgent...")
            agno_agent = AgnoAgent()
            logger.info("AgnoAgent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Agno agent: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize Agno agent: {str(e)}"
            )
    return agno_agent


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


async def post_to_slack(channel: str, text: str, thread_ts: Optional[str] = None, retries: int = 3):
    """Post a message to a Slack channel with retry logic."""
    headers = _get_slack_headers()
    
    payload = {
        "channel": channel,
        "text": text
    }
    
    if thread_ts:
        payload["thread_ts"] = thread_ts
    
    logger.info(f"Posting to Slack channel {channel}: {text[:100]}...")
    
    # Retry logic for network issues
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
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
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as e:
            if attempt < retries - 1:
                wait_time = (attempt + 1) * 2  # Exponential backoff: 2s, 4s, 6s
                logger.warning(f"Slack API timeout (attempt {attempt + 1}/{retries}), retrying in {wait_time}s...")
                import asyncio
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Slack API timeout after {retries} attempts: {e}")
                raise
        except Exception as e:
            logger.error(f"Error posting to Slack: {e}")
            raise


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
        event_id = event.get("event_ts") or event.get("ts")  # Use timestamp as unique ID
        event_ts = event.get("ts")
        
        logger.info(f"Event type: {event_type}, Channel: {event.get('channel')}, Event ID: {event_id}")
        
        # Deduplication: Check if we've already processed this event
        if event_id and event_id in processed_events:
            logger.info(f"Event {event_id} already processed, skipping")
            return JSONResponse(content={"status": "ok"})
        
        # Ignore bot messages (check both bot_id and user to prevent self-responses)
        if event.get("bot_id"):
            logger.info("Ignoring bot message (has bot_id)")
            return JSONResponse(content={"status": "ok"})
        
        # Get bot user ID to check if message is from ourselves
        bot_user_id = data.get("authorizations", [{}])[0].get("user_id")
        if event.get("user") == bot_user_id:
            logger.info("Ignoring message from bot user")
            return JSONResponse(content={"status": "ok"})
        
        # Handle app mentions and direct messages
        if event_type == "app_mention" or event_type == "message":
            # Skip if in a thread (to avoid loops)
            if event.get("thread_ts") and event.get("thread_ts") != event_ts:
                logger.info("Ignoring threaded message")
                return JSONResponse(content={"status": "ok"})
            
            # Mark event as processed
            if event_id:
                processed_events.add(event_id)
                # Clean up old events (keep last 1000)
                if len(processed_events) > 1000:
                    # Remove oldest 500
                    sorted_events = sorted(processed_events)
                    processed_events.difference_update(sorted_events[:500])
            
            channel = event.get("channel")
            user_message = event.get("text", "").strip()
            logger.info(f"User message: {user_message}")
            
            # Remove bot mention if present (format: <@U123456>)
            import re
            if bot_user_id:
                user_message = re.sub(rf"<@{bot_user_id}>", "", user_message).strip()
            # Also remove generic mentions
            user_message = re.sub(r"<@[A-Z0-9]+>", "", user_message).strip()
            
            if not user_message:
                logger.info("Empty message after cleaning")
                return JSONResponse(content={"status": "ok"})
            
            # Process with agent - route Jira/GitHub requests to Agno, others to current agent
            try:
                logger.info(f"Processing message with agent: {user_message}")
                
                # Check if this should be handled by Agno (Jira, GitHub, Calendar, or multi-tool)
                if should_use_agno(user_message):
                    try:
                        logger.info("Routing to Agno agent (Jira/GitHub/Calendar/multi-tool request)")
                        agno_instance = get_agno_agent()
                        response = await agno_instance.run(user_message)
                        logger.info(f"Agno agent response: {response[:100]}...")
                    except Exception as agno_error:
                        logger.warning(f"Agno agent failed, falling back to regular agent: {agno_error}")
                        # Fallback to regular agent
                        agent_instance = get_agent()
                        response = await agent_instance.chat(user_message)
                        logger.info(f"Fallback agent response: {response[:100]}...")
                else:
                    # Use regular agent for other requests
                    agent_instance = get_agent()
                    response = await agent_instance.chat(user_message)
                    logger.info(f"Agent response: {response[:100]}...")
                
                # Post response to Slack with retry
                await post_to_slack(channel, response, thread_ts=event_ts)
                logger.info("Successfully processed and posted response")
                
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                error_msg = f"Sorry, I encountered an error: {str(e)[:200]}"
                try:
                    await post_to_slack(channel, error_msg, thread_ts=event_ts, retries=2)
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
        # Process with agent - route Jira/GitHub/Calendar/multi-tool requests to Agno
        if should_use_agno(user_message):
            try:
                agno_instance = get_agno_agent()
                response = await agno_instance.run(user_message)
            except Exception as agno_error:
                logger.warning(f"Agno agent failed, falling back: {agno_error}")
                agent_instance = get_agent()
                response = await agent_instance.chat(user_message)
        else:
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


@app.post("/webhooks/github")
async def github_webhook(request: Request):
    """Handle GitHub webhook events."""
    try:
        from app.triggers.webhooks import handle_github_webhook
        
        payload = await request.json()
        success = await handle_github_webhook(payload)
        
        if success:
            return JSONResponse(content={"status": "ok"})
        else:
            return JSONResponse(content={"status": "ignored"}, status_code=200)
            
    except Exception as e:
        logger.error(f"GitHub webhook error: {e}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/webhooks/jira")
async def jira_webhook(request: Request):
    """Handle Jira webhook events."""
    try:
        from app.triggers.webhooks import handle_jira_webhook
        
        payload = await request.json()
        success = await handle_jira_webhook(payload)
        
        if success:
            return JSONResponse(content={"status": "ok"})
        else:
            return JSONResponse(content={"status": "ignored"}, status_code=200)
            
    except Exception as e:
        logger.error(f"Jira webhook error: {e}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)

