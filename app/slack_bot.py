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
import asyncio
from typing import List, Dict
from app.agent.conversation import ConversationalAgent
from app.agno_agent import AgnoAgent, should_use_agno
from app.slack_features import (
    generate_standup_summary,
    summarize_pr,
    summarize_jira_issue,
    get_context_suggestions,
    get_team_workload,
    create_action_buttons,
    get_user_jira_issues,
    get_user_prs
)


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


async def post_to_slack(
    channel: str, 
    text: str, 
    thread_ts: Optional[str] = None, 
    blocks: Optional[List[Dict]] = None,
    retries: int = 3
):
    """Post a message to a Slack channel with retry logic."""
    headers = _get_slack_headers()
    
    payload = {
        "channel": channel,
        "text": text
    }
    
    if thread_ts:
        payload["thread_ts"] = thread_ts
    
    if blocks:
        payload["blocks"] = blocks
    
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
                    # Handle rate limits
                    if error == "rate_limited":
                        retry_after = int(result.get("headers", {}).get("Retry-After", 1))
                        if attempt < retries - 1:
                            logger.warning(f"Rate limited, waiting {retry_after}s...")
                            import asyncio
                            await asyncio.sleep(retry_after)
                            continue
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


async def update_slack_message(channel: str, ts: str, text: str, blocks: Optional[List[Dict]] = None):
    """Update an existing Slack message."""
    headers = _get_slack_headers()
    
    payload = {
        "channel": channel,
        "ts": ts,
        "text": text
    }
    
    if blocks:
        payload["blocks"] = blocks
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://slack.com/api/chat.update",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            if not result.get("ok"):
                error = result.get("error", "unknown_error")
                logger.error(f"Slack API error updating message: {error}")
                raise Exception(f"Slack API error: {error}")
            
            return result
    except Exception as e:
        logger.error(f"Error updating Slack message: {e}")
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
            # Support thread-based conversations - use thread_ts if present, otherwise use event_ts
            # If message is in a thread (thread_ts exists), continue the conversation in that thread
            # If thread_ts == event_ts, it's the root message of a thread, so we should still use it
            thread_ts = event.get("thread_ts") if event.get("thread_ts") else event_ts
            
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
            user_id = event.get("user")
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
            
            # Post instant acknowledgment
            ack_message = "💭 Got it! Processing your request..."
            try:
                ack_result = await post_to_slack(channel, ack_message, thread_ts=thread_ts)
                ack_ts = ack_result.get("ts")
            except Exception as ack_error:
                logger.warning(f"Failed to post acknowledgment: {ack_error}")
                ack_ts = None
            
            # Check for summary requests first (before routing to agent)
            import re
            pr_match = re.search(r'(?:pr|pull\s*request|#)\s*#?(\d+)', user_message.lower())
            issue_match = re.search(r'([A-Z]+-\d+)', user_message, re.IGNORECASE)
            
            if "summarize" in user_message.lower() or "summary" in user_message.lower():
                summary_response = None
                if pr_match:
                    pr_num = int(pr_match.group(1))
                    try:
                        summary_response = await summarize_pr(pr_num)
                    except Exception as e:
                        logger.error(f"Error summarizing PR: {e}", exc_info=True)
                elif issue_match:
                    issue_key = issue_match.group(1)
                    try:
                        summary_response = await summarize_jira_issue(issue_key)
                    except Exception as e:
                        logger.error(f"Error summarizing issue: {e}", exc_info=True)
                
                if summary_response:
                    if ack_ts:
                        try:
                            await update_slack_message(channel, ack_ts, summary_response)
                            logger.info("Successfully updated with summary")
                        except:
                            await post_to_slack(channel, summary_response, thread_ts=thread_ts)
                    else:
                        await post_to_slack(channel, summary_response, thread_ts=thread_ts)
                    return JSONResponse(content={"status": "ok"})
            
            # Process with agent - route Jira/GitHub requests to Agno, others to current agent
            try:
                logger.info(f"Processing message with agent: {user_message}")
                
                # Check if this should be handled by Agno (Jira, GitHub, Calendar, or multi-tool)
                if should_use_agno(user_message):
                    try:
                        logger.info("Routing to Agno agent (Jira/GitHub/Calendar/multi-tool request)")
                        agno_instance = get_agno_agent()
                        # Extract user ID from event for memory context
                        response = await agno_instance.run(user_message, user_id=user_id)
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
                
                # Update acknowledgment with actual response, or post new message
                if ack_ts:
                    try:
                        await update_slack_message(channel, ack_ts, response)
                        logger.info("Successfully updated acknowledgment with response")
                    except Exception as update_error:
                        logger.warning(f"Failed to update message, posting new: {update_error}")
                        await post_to_slack(channel, response, thread_ts=thread_ts)
                else:
                    await post_to_slack(channel, response, thread_ts=thread_ts)
                
                logger.info("Successfully processed and posted response")
                
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                error_msg = f"Sorry, I encountered an error: {str(e)[:200]}"
                try:
                    if ack_ts:
                        await update_slack_message(channel, ack_ts, error_msg)
                    else:
                        await post_to_slack(channel, error_msg, thread_ts=thread_ts, retries=2)
                except Exception as post_error:
                    logger.error(f"Failed to post error message: {post_error}", exc_info=True)
    
    return JSONResponse(content={"status": "ok"})


@app.post("/slack/commands")
async def slack_commands(request: Request):
    """
    Handle Slack slash commands (e.g., /continuum, /my-tasks, /standup, etc.)
    """
    form_data = await request.form()
    command = form_data.get("command", "")
    user_message = form_data.get("text", "").strip()
    channel_id = form_data.get("channel_id")
    user_id = form_data.get("user_id")
    user_name = form_data.get("user_name", "")
    
    # Handle quick action shortcuts
    if command == "/my-tasks":
        try:
            issues = await get_user_jira_issues()
            if not issues:
                return JSONResponse(content={
                    "response_type": "ephemeral",
                    "text": "✅ You have no open tasks!"
                })
            
            lines = [f"📋 *Your Open Tasks ({len(issues)})*\n"]
            for issue in issues[:10]:  # Limit to 10
                status_emoji = "🔄" if "progress" in issue.get("status", "").lower() else "📝"
                lines.append(f"• {status_emoji} `{issue.get('key', 'N/A')}`: *{issue.get('summary', 'No title')}*")
                lines.append(f"  Status: {issue.get('status', 'Unknown')} | Priority: {issue.get('priority', 'None')}")
            
            if len(issues) > 10:
                lines.append(f"\n_...and {len(issues) - 10} more tasks_")
            
            # Add action buttons for first issue
            blocks = create_action_buttons(issue_key=issues[0].get("key") if issues else None)
            
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": "\n".join(lines),
                "blocks": blocks
            })
        except Exception as e:
            logger.error(f"Error in /my-tasks: {e}", exc_info=True)
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": f"❌ Error fetching tasks: {str(e)}"
            })
    
    elif command == "/my-prs":
        try:
            prs = await get_user_prs()
            if not prs:
                return JSONResponse(content={
                    "response_type": "ephemeral",
                    "text": "✅ You have no open PRs!"
                })
            
            lines = [f"🔀 *Your Open PRs ({len(prs)})*\n"]
            for pr in prs[:10]:
                state_emoji = "✅" if pr.get("state") == "open" else "⏸️"
                lines.append(f"• {state_emoji} PR #{pr.get('number', 'N/A')}: *{pr.get('title', 'No title')}*")
                lines.append(f"  State: {pr.get('state', 'unknown').upper()}")
            
            if len(prs) > 10:
                lines.append(f"\n_...and {len(prs) - 10} more PRs_")
            
            # Add action buttons for first PR
            blocks = create_action_buttons(pr_number=prs[0].get("number") if prs else None)
            
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": "\n".join(lines),
                "blocks": blocks
            })
        except Exception as e:
            logger.error(f"Error in /my-prs: {e}", exc_info=True)
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": f"❌ Error fetching PRs: {str(e)}"
            })
    
    elif command == "/standup":
        try:
            summary = await generate_standup_summary(user_id)
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": summary
            })
        except Exception as e:
            logger.error(f"Error in /standup: {e}", exc_info=True)
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": f"❌ Error generating standup: {str(e)}"
            })
    
    elif command == "/blockers":
        try:
            # Get issues with "block" keyword
            issues = await get_jira_issues('summary ~ "block" OR description ~ "block" OR status = "Blocked"')
            if not issues:
                return JSONResponse(content={
                    "response_type": "ephemeral",
                    "text": "✅ No blockers found!"
                })
            
            lines = [f"🚫 *Blockers ({len(issues)})*\n"]
            for issue in issues[:10]:
                lines.append(f"• `{issue.key}`: *{issue.summary}*")
                lines.append(f"  Status: {issue.status} | Assignee: {issue.assignee or 'Unassigned'}")
            
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": "\n".join(lines)
            })
        except Exception as e:
            logger.error(f"Error in /blockers: {e}", exc_info=True)
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": f"❌ Error fetching blockers: {str(e)}"
            })
    
    elif command == "/team-status":
        try:
            workload = await get_team_workload()
            return JSONResponse(content={
                "response_type": "in_channel",
                "text": workload
            })
        except Exception as e:
            logger.error(f"Error in /team-status: {e}", exc_info=True)
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": f"❌ Error generating team status: {str(e)}"
            })
    
    elif command == "/suggestions":
        try:
            suggestions = await get_context_suggestions(user_id)
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": suggestions
            })
        except Exception as e:
            logger.error(f"Error in /suggestions: {e}", exc_info=True)
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": f"❌ Error generating suggestions: {str(e)}"
            })
    
    elif command == "/my-week":
        try:
            from app.tools.calendar import get_this_week_availability
            from app.tools.jira import get_jira_issues
            
            # Get calendar availability
            try:
                availability = await get_this_week_availability()
                avail_dict = availability.model_dump()
            except:
                avail_dict = {}
            
            # Get tasks
            issues = await get_user_jira_issues()
            
            lines = ["📅 *Your Week Overview*\n"]
            
            # Calendar summary
            if avail_dict:
                free_hours = avail_dict.get("free_hours", 0)
                busy_hours = avail_dict.get("busy_hours", 0)
                free_slots = avail_dict.get("free_slots", [])
                events = avail_dict.get("events", [])
                
                lines.append(f"*Calendar:*")
                lines.append(f"• Free time: {free_hours:.1f} hours")
                lines.append(f"• Busy time: {busy_hours:.1f} hours")
                if free_slots:
                    lines.append(f"• {len(free_slots)} free slots available")
                if events:
                    lines.append(f"• {len(events)} events scheduled")
                lines.append("")
            
            # Tasks summary
            if issues:
                lines.append(f"*Tasks:* {len(issues)} open tasks")
                in_progress = [i for i in issues if "progress" in i.get("status", "").lower()]
                if in_progress:
                    lines.append(f"• {len(in_progress)} in progress")
                todo = [i for i in issues if "todo" in i.get("status", "").lower() or "open" in i.get("status", "").lower()]
                if todo:
                    lines.append(f"• {len(todo)} to do")
            else:
                lines.append("*Tasks:* No open tasks")
            
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": "\n".join(lines)
            })
        except Exception as e:
            logger.error(f"Error in /my-week: {e}", exc_info=True)
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": f"❌ Error generating week overview: {str(e)}"
            })
    
    # Default /continuum command
    elif command == "/continuum" or not command:
        if not user_message:
            return JSONResponse(content={
                "response_type": "ephemeral",
                "text": "Usage: /continuum <your question>\n\nQuick commands:\n• /my-tasks - Your open Jira tasks\n• /my-prs - Your open PRs\n• /my-week - This week's calendar + tasks\n• /standup - Daily standup summary\n• /blockers - Blocked items\n• /team-status - Team workload\n• /suggestions - Context-aware suggestions"
            })
        
        try:
            # Process with agent - route Jira/GitHub/Calendar/multi-tool requests to Agno
            if should_use_agno(user_message):
                try:
                    agno_instance = get_agno_agent()
                    response = await agno_instance.run(user_message, user_id=user_id)
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
    
    else:
        return JSONResponse(content={
            "response_type": "ephemeral",
            "text": f"Unknown command: {command}"
        })


@app.post("/slack/interactions")
async def slack_interactions(request: Request):
    """
    Handle Slack interactive components (buttons, etc.)
    """
    try:
        form_data = await request.form()
        payload_str = form_data.get("payload")
        
        if not payload_str:
            return JSONResponse(content={"status": "ok"})
        
        import json
        payload = json.loads(payload_str)
        action = payload.get("actions", [{}])[0]
        action_id = action.get("action_id")
        value = action.get("value", "")
        channel = payload.get("channel", {}).get("id")
        user_id = payload.get("user", {}).get("id")
        
        logger.info(f"Received interaction: {action_id} with value: {value}")
        
        # Handle different action types
        if action_id == "mark_done":
            issue_key = value.replace("mark_done_", "")
            try:
                from app.agno_tools.jira_tools import update_jira_issue_tool
                result = update_jira_issue_tool(issue_key, status="Done")
                if result.get("success"):
                    return JSONResponse(content={
                        "response_type": "ephemeral",
                        "text": f"✅ Marked {issue_key} as Done!"
                    })
                else:
                    return JSONResponse(content={
                        "response_type": "ephemeral",
                        "text": f"❌ Failed to update {issue_key}: {result.get('error')}"
                    })
            except Exception as e:
                logger.error(f"Error marking done: {e}", exc_info=True)
                return JSONResponse(content={
                    "response_type": "ephemeral",
                    "text": f"❌ Error: {str(e)}"
                })
        
        elif action_id == "assign_to_me":
            issue_key = value.replace("assign_", "")
            try:
                # Get user info from Slack
                # For now, use a placeholder - you'd need to map Slack user to Jira user
                from app.agno_tools.jira_tools import update_jira_issue_tool
                result = update_jira_issue_tool(issue_key, assignee="currentUser()")
                if result.get("success"):
                    return JSONResponse(content={
                        "response_type": "ephemeral",
                        "text": f"✅ Assigned {issue_key} to you!"
                    })
                else:
                    return JSONResponse(content={
                        "response_type": "ephemeral",
                        "text": f"❌ Failed to assign {issue_key}: {result.get('error')}"
                    })
            except Exception as e:
                logger.error(f"Error assigning: {e}", exc_info=True)
                return JSONResponse(content={
                    "response_type": "ephemeral",
                    "text": f"❌ Error: {str(e)}"
                })
        
        elif action_id == "approve_pr":
            pr_number = int(value.replace("approve_", ""))
            try:
                from app.agno_tools.github_tools import request_github_pr_review_tool
                # Note: This requests review, actual approval would need GitHub API
                return JSONResponse(content={
                    "response_type": "ephemeral",
                    "text": f"✅ Approval action for PR #{pr_number} (requires GitHub integration)"
                })
            except Exception as e:
                logger.error(f"Error approving PR: {e}", exc_info=True)
                return JSONResponse(content={
                    "response_type": "ephemeral",
                    "text": f"❌ Error: {str(e)}"
                })
        
        return JSONResponse(content={"status": "ok"})
        
    except Exception as e:
        logger.error(f"Error handling interaction: {e}", exc_info=True)
        return JSONResponse(content={"status": "ok"})


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

