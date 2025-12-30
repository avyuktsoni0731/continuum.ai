# Continuum.ai

<div align="center">

**An AI-powered productivity agent that unifies Jira, GitHub, and Google Calendar through natural language in Slack**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Features](#-features) • [Quick Start](#-quick-start) • [Architecture](#-architecture) • [Documentation](#-documentation) • [Contributing](#-contributing)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [API Reference](#-api-reference)
- [Deployment](#-deployment)
- [Development](#-development)
- [Documentation](#-documentation)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 Overview

**Continuum.ai** is an intelligent productivity agent that eliminates context switching by providing unified access to Jira, GitHub, and Google Calendar through natural language in Slack. It understands context, remembers conversations, and orchestrates complex workflows across multiple tools.

### The Problem

Developers waste 30-40% of their time context-switching between:

- **Jira** for task management
- **GitHub** for code reviews and PR tracking
- **Google Calendar** for scheduling and availability

### The Solution

Continuum.ai brings all these tools together in one intelligent interface:

- **Natural Language Interface** - Ask questions in plain English
- **Context-Aware** - Remembers team context, skills, and preferences
- **Multi-Tool Orchestration** - Executes complex workflows across platforms
- **Persistent Memory** - Retains conversation history and team knowledge
- **Proactive Features** - Auto-summaries, suggestions, and workload dashboards

---

## ✨ Features

### Core Capabilities

- **📋 Task Management**

  - Query Jira issues, create/update tasks, check board status
  - Interactive buttons for quick actions (Mark Done, Assign to Me)
  - Smart delegation recommendations based on team skills and workload

- **🔀 PR Tracking**

  - Monitor PRs, check CI/CD status, review approvals
  - PR summaries with change overview and merge readiness
  - Request reviews and manage assignees

- **📅 Calendar Integration**

  - Check availability, schedule meetings, find free slots
  - Create calendar events linked to Jira issues
  - Multi-tool orchestration (e.g., "Schedule meeting about KAN-123")

- **🤝 Smart Delegation**

  - Context-aware recommendations based on:
    - Team member skills (stored in persistent memory)
    - Current workload
    - Historical contributions
    - Task requirements

- **📊 Auto-Summaries**
  - Daily standup generation (`/standup`)
  - PR summaries with CI status and review counts
  - Jira issue summaries with context
  - Team workload dashboards

### Slack Features

- **⚡ Instant Acknowledgment** - Immediate response while processing
- **🧵 Thread-Based Conversations** - Maintain context across messages
- **⌨️ Quick Action Shortcuts** - Slash commands for common queries
- **🔘 Interactive Buttons** - One-click actions on tasks and PRs
- **💡 Context-Aware Suggestions** - Proactive recommendations
- **📈 Team Workload Dashboard** - Visualize team capacity

### Slash Commands

| Command        | Description                           |
| -------------- | ------------------------------------- |
| `/my-tasks`    | View all your open Jira tasks         |
| `/my-prs`      | View all your open pull requests      |
| `/my-week`     | This week's calendar + tasks overview |
| `/standup`     | Auto-generated daily standup summary  |
| `/blockers`    | Find all blocked items                |
| `/team-status` | Team workload dashboard               |
| `/suggestions` | Context-aware suggestions             |

---

## 🏗️ Architecture

### System Architecture

<!-- PLACEHOLDER: Architecture Diagram -->

```
[Architecture Diagram Placeholder]
See docs/ARCHITECTURE_DIAGRAMS.md for detailed Mermaid diagrams
```

**Key Components:**

- **FastAPI Application** (`app/slack_bot.py`) - Main Slack bot server
- **MCP Server** (`app/server.py`) - Model Context Protocol server
- **Agno Agent** (`app/agno_agent.py`) - Specialized agent for Jira/GitHub/Calendar
- **Conversational Agent** (`app/agent/conversation.py`) - General chat agent
- **Tool Layer** (`app/agno_tools/`, `app/tools/`) - API client wrappers
- **Feature Layer** (`app/slack_features.py`) - Slack-specific features
- **Trigger System** (`app/triggers/`) - Webhooks and scheduled tasks
- **Delegation Engine** (`app/delegation/`) - Smart task assignment
- **Policy Engine** (`app/policy/`) - Decision-making rules

### Process Flow

<!-- PLACEHOLDER: Process Flow Diagram -->

```
[Process Flow Diagram Placeholder]
See docs/ARCHITECTURE_DIAGRAMS.md for detailed flow diagrams
```

### Technology Stack

- **Backend Framework**: FastAPI (Python)
- **Agent Framework**: Agno
- **LLM**: Google Gemini 3 Pro
- **Database**: MongoDB (persistent memory)
- **APIs**:
  - Slack API (Events, Slash Commands, Interactive Components)
  - Jira API v3 + Agile API
  - GitHub REST API
  - Google Calendar API
- **Deployment**: EC2 (Ubuntu), systemd services

### Data Flow

```
User Request → Slack → FastAPI Router
                    ↓
            [Route Decision]
                    ↓
    ┌───────────────┴───────────────┐
    ↓                               ↓
Agno Agent                    Conversational Agent
(Jira/GitHub/Calendar)        (General Chat)
    ↓                               ↓
Tool Execution ←──────────→ API Calls
    ↓                               ↓
MongoDB Memory ←──────────→ Response Formatting
    ↓                               ↓
            Slack Response ←────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- MongoDB (local or cloud)
- Slack workspace with admin access
- Jira Cloud account
- GitHub account
- Google Cloud Project (for Calendar API)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/continuum.ai.git
cd continuum.ai
```

### 2. Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment

Copy `env.example` to `.env` and fill in your credentials:

```bash
cp env.example .env
```

Edit `.env` with your credentials (see [Configuration](#-configuration) section).

### 4. Run the Application

**Development Mode:**

```bash
# Start Slack Bot
uvicorn app.slack_bot:app --host 0.0.0.0 --port 3000 --reload

# Start MCP Server (in another terminal)
uvicorn app.server:app --host 0.0.0.0 --port 8000 --reload
```

**Production Mode (with systemd):**

```bash
# Make script executable
chmod +x manage_services.sh

# Start services
./manage_services.sh start

# Check status
./manage_services.sh status

# View logs
./manage_services.sh logs
```

---

## ⚙️ Installation

### Detailed Setup Instructions

#### 1. Python Environment

```bash
# Create virtual environment
python3.9 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### 2. MongoDB Setup

**Local MongoDB:**

```bash
# Install MongoDB (Ubuntu)
sudo apt-get install mongodb

# Start MongoDB
sudo systemctl start mongodb
sudo systemctl enable mongodb
```

**MongoDB Atlas (Cloud):**

1. Create account at [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
2. Create a cluster
3. Get connection string
4. Add to `.env` as `MONGODB_URL`

#### 3. Slack App Configuration

1. Go to [Slack API](https://api.slack.com/apps)
2. Create a new app
3. Configure OAuth & Permissions:

   - Bot Token Scopes:
     - `app_mentions:read`
     - `channels:history`
     - `chat:write`
     - `commands`
     - `im:history`
     - `im:write`
     - `users:read`
   - User Token Scopes (if needed):
     - `channels:read`
     - `users:read`

4. Enable Event Subscriptions:

   - Request URL: `https://your-domain.com/slack/events`
   - Subscribe to bot events:
     - `app_mentions`
     - `message.channels`
     - `message.im`
     - `message.groups`

5. Enable Interactivity:

   - Request URL: `https://your-domain.com/slack/interactions`

6. Create Slash Commands:

   - `/my-tasks`, `/my-prs`, `/my-week`, `/standup`, `/blockers`, `/team-status`, `/suggestions`
   - Request URL: `https://your-domain.com/slack/commands`

7. Install app to workspace and copy tokens

#### 4. Jira Setup

1. Go to [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Create API token
3. Get your Jira URL (e.g., `https://your-domain.atlassian.net`)
4. Add credentials to `.env`

#### 5. GitHub Setup

1. Go to [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
2. Generate token with scopes:
   - `repo` (full control of private repositories)
   - `read:org` (read org membership)
3. Add token to `.env`

#### 6. Google Calendar Setup

**Option A: Service Account (Recommended for Production)**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project or select existing
3. Enable Google Calendar API
4. Create Service Account:
   - Go to IAM & Admin > Service Accounts
   - Create service account
   - Download JSON key file
   - Share calendar with service account email (grant "Make changes to events" permission)
5. Add path to JSON file in `.env`

**Option B: OAuth2 (For Development)**

1. Create OAuth 2.0 credentials in Google Cloud Console
2. Download client secrets JSON
3. Run OAuth flow on first use
4. Add credentials path to `.env`

See `docs/GCP_CREDENTIALS_EC2.md` for detailed instructions.

---

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SLACK_SIGNING_SECRET=your-signing-secret

# Jira Configuration
JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-jira-api-token

# GitHub Configuration
GITHUB_TOKEN=your-github-personal-access-token
GITHUB_OWNER=your-org-or-username
GITHUB_REPO=your-repo-name

# Google Calendar Configuration
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json
# OR for OAuth2:
GOOGLE_CLIENT_SECRETS_FILE=path/to/client-secrets.json
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=us-central1

# MongoDB Configuration
MONGODB_URL=mongodb://localhost:27017/continuum
# OR for MongoDB Atlas:
MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/continuum

# Optional: Logging
LOG_LEVEL=INFO
```

### Configuration Files

- **`.env`** - Environment variables (not committed to git)
- **`env.example`** - Template for environment variables
- **`manage_services.sh`** - Service management script

---

## 📖 Usage

### Natural Language Queries

Tag the bot in Slack and ask questions:

```
@continuum What are my open tasks?
@continuum Show me PRs that need my review
@continuum What's my availability this week?
@continuum Schedule a meeting tomorrow at 2pm about KAN-123
@continuum Who should I assign this task to?
@continuum Summarize PR #42
@continuum Summarize issue KAN-123
```

### Slash Commands

Use slash commands for quick access:

```
/my-tasks          # View all open Jira tasks
/my-prs            # View all open PRs
/my-week           # This week's overview
/standup           # Generate daily standup
/blockers          # Find blocked items
/team-status       # Team workload dashboard
/suggestions       # Context-aware suggestions
```

### Interactive Features

**Action Buttons:**

- Click "Mark Done" to close a Jira issue
- Click "Assign to Me" to assign an issue to yourself
- Click "Review" to review a PR

**Thread Conversations:**

- Reply to bot messages in threads to maintain context
- Reference previous messages naturally

### Example Workflows

**1. Morning Standup:**

```
/standup
```

**2. Task Delegation:**

```
@continuum The CI/CD pipeline is causing issues, whom should I assign the task to?
```

**3. Multi-Tool Orchestration:**

```
@continuum Check available slots for avyukt, assign PR #42 to him, create a Jira issue with him assigned, and schedule a meeting about it
```

**4. PR Review:**

```
@continuum What PRs need my review?
@continuum Summarize PR #42
```

---

## 📡 API Reference

### Slack Bot Endpoints

- `POST /slack/events` - Slack event webhook
- `POST /slack/commands` - Slash command handler
- `POST /slack/interactions` - Interactive component handler
- `GET /health` - Health check endpoint
- `POST /webhooks/github` - GitHub webhook handler
- `POST /webhooks/jira` - Jira webhook handler

### MCP Server Endpoints

- `GET /mcp/` - MCP server root
- `POST /mcp/tools/call` - Tool execution endpoint

### Tool Functions

**Jira Tools:**

- `get_jira_issues_tool` - Query Jira issues
- `get_jira_issue_tool` - Get single issue
- `create_jira_issue_tool` - Create new issue
- `update_jira_issue_tool` - Update issue
- `get_jira_projects_tool` - List projects
- `get_jira_boards_tool` - List boards
- `get_jira_board_issues_tool` - Get board issues
- `find_jira_user_tool` - Find user by name/email

**GitHub Tools:**

- `get_github_pulls_tool` - List pull requests
- `get_github_pull_tool` - Get single PR
- `get_github_pr_context_tool` - Get comprehensive PR context
- `get_github_pr_checks_tool` - Get CI/CD status
- `get_github_pr_reviews_tool` - Get reviews
- `create_github_pr_tool` - Create PR
- `update_github_pr_tool` - Update PR
- `update_github_pr_assignees_tool` - Manage assignees
- `update_github_pr_labels_tool` - Manage labels
- `request_github_pr_review_tool` - Request review

**Calendar Tools:**

- `list_calendars_tool` - List accessible calendars
- `get_calendar_events_tool` - Get events for date range
- `get_calendar_availability_tool` - Get availability with free slots
- `get_today_events_tool` - Get today's events
- `get_this_week_availability_tool` - Get week availability
- `create_calendar_event_tool` - Create calendar event

---

## 🚢 Deployment

### EC2 Deployment

<!-- PLACEHOLDER: EC2 Screenshot -->

```
[EC2 Instance Screenshot Placeholder]
```

**1. Launch EC2 Instance:**

- AMI: Ubuntu 22.04 LTS
- Instance Type: t3.medium or larger
- Security Group: Allow HTTP (80), HTTPS (443), and custom ports (3000, 8000)

**2. Initial Setup:**

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Python and dependencies
sudo apt-get install -y python3.9 python3.9-venv python3-pip git

# Install MongoDB (if using local)
sudo apt-get install -y mongodb

# Clone repository
git clone https://github.com/yourusername/continuum.ai.git
cd continuum.ai
```

**3. Configure Environment:**

```bash
# Create .env file
cp env.example .env
nano .env  # Edit with your credentials
```

**4. Install Application:**

```bash
# Create virtual environment
python3.9 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**5. Set Up systemd Services:**

Create service files (see `docs/EC2_SYSTEMD_SETUP.md` for details):

```bash
# Slack Bot Service
sudo nano /etc/systemd/system/continuum-slack-bot.service

# MCP Server Service
sudo nano /etc/systemd/system/continuum-mcp.service
```

**6. Start Services:**

```bash
# Make management script executable
chmod +x manage_services.sh

# Start services
./manage_services.sh start

# Enable on boot
./manage_services.sh enable
```

**7. Set Up Reverse Proxy (Optional):**

Use Nginx or Cloudflare Tunnel for HTTPS:

```bash
# Install Nginx
sudo apt-get install -y nginx

# Configure Nginx (see docs/NGROK_QUICK_SETUP.md for Cloudflare Tunnel alternative)
```

### Cloudflare Tunnel (Alternative)

For HTTPS without exposing ports:

```bash
# Install cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Authenticate
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create continuum

# Configure tunnel
# Edit ~/.cloudflared/config.yml
```

See `docs/NGROK_QUICK_SETUP.md` and `docs/CLOUDFLARE_TUNNEL_SETUP.md` for details.

### Monitoring

**View Logs:**

```bash
# All services
./manage_services.sh logs

# Individual services
./manage_services.sh logs-slack
./manage_services.sh logs-mcp
```

**Check Status:**

```bash
./manage_services.sh status
```

**Health Checks:**

```bash
# Slack Bot
curl http://localhost:3000/health

# MCP Server
curl http://localhost:8000/mcp/
```

---

## 💻 Development

### Project Structure

```
continuum.ai/
├── app/
│   ├── __init__.py
│   ├── slack_bot.py              # Main Slack bot FastAPI app
│   ├── server.py                 # MCP server
│   ├── agno_agent.py             # Agno-based agent
│   ├── slack_features.py         # Slack-specific features
│   ├── streamlit_app.py          # Streamlit frontend (optional)
│   ├── agent/
│   │   └── conversation.py       # Conversational agent
│   ├── agno_tools/               # Agno tool wrappers
│   │   ├── jira_tools.py
│   │   ├── github_tools.py
│   │   └── calendar_tools.py
│   ├── tools/                    # Core API clients
│   │   ├── jira.py
│   │   ├── github.py
│   │   └── calendar.py
│   ├── triggers/                 # Trigger system
│   │   ├── scheduler.py
│   │   ├── webhooks.py
│   │   ├── detector.py
│   │   └── processor.py
│   ├── delegation/               # Delegation engine
│   │   ├── selector.py
│   │   ├── notifier.py
│   │   └── config.py
│   └── policy/                   # Policy engine
│       ├── decision.py
│       ├── rules.py
│       └── scoring.py
├── docs/                         # Documentation
│   ├── ARCHITECTURE_DIAGRAMS.md
│   ├── PRESENTATION_SLIDES.md
│   ├── SLACK_FEATURES_GUIDE.md
│   └── ...
├── manage_services.sh            # Service management script
├── requirements.txt              # Python dependencies
├── env.example                   # Environment template
├── LICENSE                       # MIT License
└── README.md                     # This file
```

### Running in Development

```bash
# Activate virtual environment
source .venv/bin/activate

# Start Slack Bot (with auto-reload)
uvicorn app.slack_bot:app --host 0.0.0.0 --port 3000 --reload

# Start MCP Server (with auto-reload)
uvicorn app.server:app --host 0.0.0.0 --port 8000 --reload
```

### Testing

```bash
# Test Slack bot health
curl http://localhost:3000/health

# Test MCP server
curl http://localhost:8000/mcp/

# Run verification script
python final_verify.py
```

### Code Style

- Follow PEP 8 Python style guide
- Use type hints where possible
- Document functions with docstrings
- Keep functions focused and modular

---

## 📚 Documentation

### Available Documentation

- **[Architecture Diagrams](docs/ARCHITECTURE_DIAGRAMS.md)** - System architecture and process flows
- **[Presentation Slides](docs/PRESENTATION_SLIDES.md)** - Presentation content and demo script
- **[Slack Features Guide](docs/SLACK_FEATURES_GUIDE.md)** - Detailed feature documentation
- **[EC2 Setup Guide](docs/EC2_SETUP_SIMPLE.md)** - EC2 deployment instructions
- **[EC2 systemd Setup](docs/EC2_SYSTEMD_SETUP.md)** - Service configuration
- **[GCP Credentials Setup](docs/GCP_CREDENTIALS_EC2.md)** - Google Calendar API setup
- **[Slack Bot Setup](docs/SLACK_BOT_SETUP.md)** - Slack app configuration
- **[Slack Bot Testing](docs/SLACK_BOT_TESTING.md)** - Testing guide
- **[Slack Bot Troubleshooting](docs/SLACK_BOT_TROUBLESHOOTING.md)** - Common issues and solutions
- **[Trigger System](docs/TRIGGER_SYSTEM_README.md)** - Webhook and scheduler system
- **[Delegation Engine](docs/DELEGATION_ENGINE_README.md)** - Smart task assignment
- **[Policy Engine](docs/POLICY_ENGINE_README.md)** - Decision-making rules
- **[Streamlit Frontend](docs/STREAMLIT_FRONTEND_GUIDE.md)** - Optional web UI

### Screenshots

<!-- PLACEHOLDER: Slack Bot Interface Screenshots -->

```
[Slack Bot Interface Screenshots Placeholder]
- Main conversation interface
- Slash commands menu
- Interactive buttons
- Standup summary example
- Team workload dashboard
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Make your changes**
4. **Commit your changes** (`git commit -m 'Add some amazing feature'`)
5. **Push to the branch** (`git push origin feature/amazing-feature`)
6. **Open a Pull Request**

### Development Guidelines

- Write clear commit messages
- Add tests for new features
- Update documentation as needed
- Follow existing code style
- Ensure all tests pass

### Reporting Issues

If you find a bug or have a feature request, please open an issue on GitHub with:

- Clear description of the problem/feature
- Steps to reproduce (for bugs)
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Agno Framework** - For scalable agent orchestration
- **Google Gemini** - For advanced LLM capabilities
- **FastAPI** - For the excellent web framework
- **Slack API** - For seamless integration

---

## 📞 Support

For questions, issues, or contributions:

- **GitHub Issues**: [Open an issue](https://github.com/yourusername/continuum.ai/issues)
- **Documentation**: See the [docs/](docs/) directory
- **Email**: [Your email]

---

<div align="center">

**Made with ❤️ by the Continuum.ai team**

[⭐ Star us on GitHub](https://github.com/yourusername/continuum.ai) • [📖 Read the Docs](docs/) • [🐛 Report Bug](https://github.com/yourusername/continuum.ai/issues)

</div>
