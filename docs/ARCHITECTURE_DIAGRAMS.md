# Continuum.ai Architecture Diagrams

This document contains Mermaid diagrams documenting the system architecture, process flows, and component interactions.

## 1. System Architecture

```mermaid
graph TB
    subgraph "External Services"
        Slack[Slack Workspace]
        Jira[Jira Cloud API]
        GitHub[GitHub API]
        Calendar[Google Calendar API]
        MongoDB[(MongoDB<br/>Persistent Memory)]
    end

    subgraph "Application Layer"
        FastAPI[FastAPI Application<br/>slack_bot.py]
        MCP[MCP Server<br/>server.py]
    end

    subgraph "Agent Layer"
        Router[Request Router<br/>should_use_agno]
        AgnoAgent[Agno Agent<br/>Gemini 3 Pro]
        ConvAgent[Conversational Agent<br/>Gemini]
    end

    subgraph "Tool Layer"
        JiraTools[Jira Tools<br/>jira_tools.py]
        GitHubTools[GitHub Tools<br/>github_tools.py]
        CalendarTools[Calendar Tools<br/>calendar_tools.py]
    end

    subgraph "Core Services"
        JiraAPI[Jira API Client<br/>tools/jira.py]
        GitHubAPI[GitHub API Client<br/>tools/github.py]
        CalendarAPI[Calendar API Client<br/>tools/calendar.py]
    end

    subgraph "Feature Layer"
        SlackFeatures[Slack Features<br/>slack_features.py]
        Triggers[Trigger System<br/>scheduler, webhooks]
        Delegation[Delegation Engine]
        Policy[Policy Engine]
    end

    Slack -->|Events/Commands| FastAPI
    FastAPI -->|Route Request| Router
    Router -->|Jira/GitHub/Calendar| AgnoAgent
    Router -->|General Chat| ConvAgent

    AgnoAgent -->|Use Tools| JiraTools
    AgnoAgent -->|Use Tools| GitHubTools
    AgnoAgent -->|Use Tools| CalendarTools
    AgnoAgent -->|Store Memory| MongoDB

    ConvAgent -->|Use Tools| JiraTools
    ConvAgent -->|Use Tools| GitHubTools

    JiraTools -->|API Calls| JiraAPI
    GitHubTools -->|API Calls| GitHubAPI
    CalendarTools -->|API Calls| CalendarAPI

    JiraAPI -->|HTTP| Jira
    GitHubAPI -->|HTTP| GitHub
    CalendarAPI -->|HTTP| Calendar

    FastAPI -->|Quick Actions| SlackFeatures
    SlackFeatures -->|Fetch Data| JiraAPI
    SlackFeatures -->|Fetch Data| GitHubAPI
    SlackFeatures -->|Fetch Data| CalendarAPI

    Triggers -->|Webhooks| Jira
    Triggers -->|Webhooks| GitHub
    Triggers -->|Notifications| FastAPI

    FastAPI -->|Response| Slack

    style AgnoAgent fill:#4CAF50
    style ConvAgent fill:#2196F3
    style MongoDB fill:#FF9800
    style FastAPI fill:#9C27B0
```

## 2. Request Processing Flow

```mermaid
flowchart TD
    Start([User sends message/command]) --> CheckType{Request Type?}

    CheckType -->|Slack Event| EventHandler[Slack Event Handler]
    CheckType -->|Slash Command| CommandHandler[Slash Command Handler]
    CheckType -->|Interaction| InteractionHandler[Interaction Handler]

    EventHandler --> CheckMention{Is Bot Mentioned?}
    CheckMention -->|Yes| ExtractMessage[Extract User Message]
    CheckMention -->|No| End1([End - Ignore])

    CommandHandler --> IdentifyCommand{Command Type?}
    IdentifyCommand -->|/my-tasks| QuickAction1[Get User Jira Issues]
    IdentifyCommand -->|/my-prs| QuickAction2[Get User PRs]
    IdentifyCommand -->|/standup| QuickAction3[Generate Standup]
    IdentifyCommand -->|/continuum| ExtractMessage
    IdentifyCommand -->|Other| QuickAction4[Other Quick Actions]

    QuickAction1 --> FormatResponse1[Format Response]
    QuickAction2 --> FormatResponse2[Format Response]
    QuickAction3 --> FormatResponse3[Format Response]
    QuickAction4 --> FormatResponse4[Format Response]

    ExtractMessage --> PostAck[Post Instant Acknowledgment]
    PostAck --> RouteRequest{Route Request}

    RouteRequest -->|Jira/GitHub/Calendar/Memory| UseAgno[Use Agno Agent]
    RouteRequest -->|General Chat| UseConv[Use Conversational Agent]

    UseAgno --> AgnoProcess[Agno Processes Request]
    AgnoProcess --> AgnoTools[Agno Uses Tools]
    AgnoTools --> AgnoResponse[Agno Generates Response]

    UseConv --> ConvProcess[Conversational Agent Processes]
    ConvProcess --> ConvResponse[Agent Generates Response]

    AgnoResponse --> UpdateMessage[Update Slack Message]
    ConvResponse --> UpdateMessage
    FormatResponse1 --> PostResponse1[Post to Slack]
    FormatResponse2 --> PostResponse2[Post to Slack]
    FormatResponse3 --> PostResponse3[Post to Slack]
    FormatResponse4 --> PostResponse4[Post to Slack]

    UpdateMessage --> End2([End])
    PostResponse1 --> End2
    PostResponse2 --> End2
    PostResponse3 --> End2
    PostResponse4 --> End2

    InteractionHandler --> HandleAction{Action Type?}
    HandleAction -->|mark_done| UpdateJira[Update Jira Issue]
    HandleAction -->|assign_to_me| AssignIssue[Assign Issue]
    HandleAction -->|approve_pr| ApprovePR[Approve PR]
    HandleAction -->|Other| OtherAction[Handle Other Action]

    UpdateJira --> ActionResponse[Return Action Response]
    AssignIssue --> ActionResponse
    ApprovePR --> ActionResponse
    OtherAction --> ActionResponse
    ActionResponse --> End2

    style UseAgno fill:#4CAF50
    style UseConv fill:#2196F3
    style PostAck fill:#FF9800
```

## 3. Agent Routing Logic

```mermaid
flowchart TD
    Input[User Message] --> CheckKeywords{Contains Keywords?}

    CheckKeywords -->|jira, issue, task, board| RouteAgno1[Route to Agno]
    CheckKeywords -->|github, pr, pull request, commit| RouteAgno2[Route to Agno]
    CheckKeywords -->|calendar, schedule, meeting, availability| RouteAgno3[Route to Agno]
    CheckKeywords -->|delegate, recommend, assign, team| RouteAgno4[Route to Agno]
    CheckKeywords -->|memory, remember, recall| RouteAgno5[Route to Agno]
    CheckKeywords -->|None| CheckMultiTool{Multi-tool Request?}

    CheckMultiTool -->|Yes| RouteAgno6[Route to Agno]
    CheckMultiTool -->|No| RouteConv[Route to Conversational Agent]

    RouteAgno1 --> AgnoAgent[Agno Agent]
    RouteAgno2 --> AgnoAgent
    RouteAgno3 --> AgnoAgent
    RouteAgno4 --> AgnoAgent
    RouteAgno5 --> AgnoAgent
    RouteAgno6 --> AgnoAgent

    RouteConv --> ConvAgent[Conversational Agent]

    AgnoAgent --> AgnoTools[Agno Tool Execution]
    AgnoTools --> JiraTools[Jira Tools]
    AgnoTools --> GitHubTools[GitHub Tools]
    AgnoTools --> CalendarTools[Calendar Tools]

    ConvAgent --> ConvTools[Conversational Tools]
    ConvTools --> GeneralTools[General Purpose Tools]

    JiraTools --> JiraAPI[Jira API]
    GitHubTools --> GitHubAPI[GitHub API]
    CalendarTools --> CalendarAPI[Calendar API]

    JiraAPI --> Response1[Formatted Response]
    GitHubAPI --> Response1
    CalendarAPI --> Response1
    GeneralTools --> Response2[Formatted Response]

    Response1 --> Slack[Post to Slack]
    Response2 --> Slack

    style AgnoAgent fill:#4CAF50
    style ConvAgent fill:#2196F3
    style RouteAgno1 fill:#C8E6C9
    style RouteAgno2 fill:#C8E6C9
    style RouteAgno3 fill:#C8E6C9
    style RouteAgno4 fill:#C8E6C9
    style RouteAgno5 fill:#C8E6C9
    style RouteAgno6 fill:#C8E6C9
```

## 4. Agno Agent Tool Execution Flow

```mermaid
sequenceDiagram
    participant User
    participant Slack
    participant Router
    participant AgnoAgent
    participant Gemini
    participant Tools
    participant JiraAPI
    participant GitHubAPI
    participant CalendarAPI
    participant MongoDB

    User->>Slack: Send message "@continuum show me my tasks"
    Slack->>Router: POST /slack/events
    Router->>Router: should_use_agno() = true
    Router->>AgnoAgent: run(message, user_id)
    AgnoAgent->>Slack: Post "💭 Got it! Processing..."

    AgnoAgent->>Gemini: arun(message) with tools
    Gemini->>Gemini: Analyze request
    Gemini->>Tools: get_jira_issues_tool()
    Tools->>JiraAPI: GET /rest/api/3/search
    JiraAPI-->>Tools: Issues data
    Tools-->>Gemini: Formatted issues

    Gemini->>Gemini: Generate response
    Gemini-->>AgnoAgent: Formatted response
    AgnoAgent->>MongoDB: Store conversation history
    AgnoAgent->>Slack: Update message with response

    Note over AgnoAgent,MongoDB: Persistent memory across sessions
```

## 5. Multi-Tool Orchestration Flow

```mermaid
flowchart TD
    Start([Complex Request:<br/>Schedule meeting considering<br/>calendar and tasks]) --> AgnoAgent[Agno Agent Receives Request]

    AgnoAgent --> Step1[Step 1: Get Calendar Availability]
    Step1 --> CalendarTool[get_calendar_availability_tool]
    CalendarTool --> CalendarAPI[Calendar API]
    CalendarAPI --> FreeSlots[Free Time Slots]

    FreeSlots --> Step2[Step 2: Get User Tasks]
    Step2 --> JiraTool[get_jira_issues_tool]
    JiraTool --> JiraAPI[Jira API]
    JiraAPI --> Tasks[User Tasks]

    Tasks --> Step3[Step 3: Analyze Context]
    Step3 --> Reasoning[Agent Reasoning]
    Reasoning --> CheckConflict{Time Conflict?}

    CheckConflict -->|Yes| SuggestAlternative[Suggest Alternative Time]
    CheckConflict -->|No| ProceedCreate[Proceed with Creation]

    SuggestAlternative --> Step4[Step 4: Create Event]
    ProceedCreate --> Step4

    Step4 --> CreateTool[create_calendar_event_tool]
    CreateTool --> CalendarAPI2[Calendar API]
    CalendarAPI2 --> EventCreated[Event Created]

    EventCreated --> Step5[Step 5: Update Related Task]
    Step5 --> UpdateTool[update_jira_issue_tool]
    UpdateTool --> JiraAPI2[Jira API]
    JiraAPI2 --> TaskUpdated[Task Updated]

    TaskUpdated --> FormatResponse[Format Complete Response]
    FormatResponse --> Response[Return to User]

    style AgnoAgent fill:#4CAF50
    style Reasoning fill:#FF9800
    style EventCreated fill:#4CAF50
    style TaskUpdated fill:#4CAF50
```

## 6. Data Flow Architecture

```mermaid
graph LR
    subgraph "Data Sources"
        JiraData[(Jira Data)]
        GitHubData[(GitHub Data)]
        CalendarData[(Calendar Data)]
    end

    subgraph "API Layer"
        JiraAPI[Jira API Client]
        GitHubAPI[GitHub API Client]
        CalendarAPI[Calendar API Client]
    end

    subgraph "Tool Wrappers"
        JiraTools[Jira Tool Wrappers]
        GitHubTools[GitHub Tool Wrappers]
        CalendarTools[Calendar Tool Wrappers]
    end

    subgraph "Agent Processing"
        AgnoAgent[Agno Agent]
        Memory[MongoDB Memory]
    end

    subgraph "Response Formatting"
        Formatter[Response Formatter]
        SlackFormat[Slack Formatting]
    end

    subgraph "Output"
        Slack[Slack Channel]
    end

    JiraData -->|HTTP REST| JiraAPI
    GitHubData -->|HTTP REST| GitHubAPI
    CalendarData -->|HTTP REST| CalendarAPI

    JiraAPI -->|Pydantic Models| JiraTools
    GitHubAPI -->|Pydantic Models| GitHubTools
    CalendarAPI -->|Pydantic Models| CalendarTools

    JiraTools -->|Tool Calls| AgnoAgent
    GitHubTools -->|Tool Calls| AgnoAgent
    CalendarTools -->|Tool Calls| AgnoAgent

    AgnoAgent <-->|Read/Write| Memory

    AgnoAgent -->|Structured Data| Formatter
    Formatter -->|Markdown| SlackFormat
    SlackFormat -->|Slack Blocks| Slack

    style AgnoAgent fill:#4CAF50
    style Memory fill:#FF9800
    style Formatter fill:#2196F3
```

## 7. Trigger System Flow

```mermaid
flowchart TD
    Start([External Event]) --> EventType{Event Type?}

    EventType -->|Jira Webhook| JiraWebhook[Jira Webhook Handler]
    EventType -->|GitHub Webhook| GitHubWebhook[GitHub Webhook Handler]
    EventType -->|Scheduled| Scheduler[Scheduler Trigger]

    JiraWebhook --> ParseJira[Parse Jira Event]
    ParseJira --> CheckChange{Change Type?}
    CheckChange -->|Issue Created| NotifyCreate[Notify: Issue Created]
    CheckChange -->|Issue Updated| NotifyUpdate[Notify: Issue Updated]
    CheckChange -->|Status Changed| NotifyStatus[Notify: Status Change]
    CheckChange -->|Assignee Changed| NotifyAssign[Notify: Assignee Change]

    GitHubWebhook --> ParseGitHub[Parse GitHub Event]
    ParseGitHub --> CheckPR{PR Event?}
    CheckPR -->|PR Opened| NotifyPROpen[Notify: PR Opened]
    CheckPR -->|PR Merged| NotifyPRMerge[Notify: PR Merged]
    CheckPR -->|Review Submitted| NotifyReview[Notify: Review Submitted]
    CheckPR -->|CI Status Changed| NotifyCI[Notify: CI Status]

    Scheduler --> CheckSchedule{Schedule Type?}
    CheckSchedule -->|Daily Standup| GenerateStandup[Generate Standup Summary]
    CheckSchedule -->|Weekly Report| GenerateReport[Generate Weekly Report]
    CheckSchedule -->|Reminder| SendReminder[Send Reminder]

    NotifyCreate --> PolicyEngine[Policy Engine]
    NotifyUpdate --> PolicyEngine
    NotifyStatus --> PolicyEngine
    NotifyAssign --> PolicyEngine
    NotifyPROpen --> PolicyEngine
    NotifyPRMerge --> PolicyEngine
    NotifyReview --> PolicyEngine
    NotifyCI --> PolicyEngine
    GenerateStandup --> PolicyEngine
    GenerateReport --> PolicyEngine
    SendReminder --> PolicyEngine

    PolicyEngine --> EvaluateRules[Evaluate Rules]
    EvaluateRules --> Decision{Action Required?}
    Decision -->|Yes| ExecuteAction[Execute Action]
    Decision -->|No| LogEvent[Log Event]

    ExecuteAction --> NotifySlack[Post to Slack]
    LogEvent --> End([End])
    NotifySlack --> End

    style PolicyEngine fill:#FF9800
    style ExecuteAction fill:#4CAF50
```

## 8. Memory & Context Persistence

```mermaid
graph TB
    subgraph "User Interaction"
        UserMessage[User Message]
        UserID[User ID / Session ID]
    end

    subgraph "Agno Agent"
        Agent[Agno Agent]
        SessionID[Session ID = User ID]
    end

    subgraph "MongoDB Storage"
        SessionMemory[(Session History)]
        UserMemory[(User Memories)]
        TeamData[(Team Member Data)]
    end

    subgraph "Memory Types"
        ConversationHistory[Conversation History]
        UserPreferences[User Preferences]
        TeamInfo[Team Member Info<br/>GitHub ID, Jira ID, Skills]
        DelegationHistory[Delegation History]
        Recommendations[Recommendations]
    end

    UserMessage --> Agent
    UserID --> SessionID
    SessionID --> Agent

    Agent -->|Store| SessionMemory
    Agent -->|Retrieve| SessionMemory
    Agent -->|Store| UserMemory
    Agent -->|Retrieve| UserMemory
    Agent -->|Store| TeamData
    Agent -->|Retrieve| TeamData

    SessionMemory --> ConversationHistory
    UserMemory --> UserPreferences
    TeamData --> TeamInfo
    TeamData --> DelegationHistory
    TeamData --> Recommendations

    ConversationHistory -->|Context| Agent
    UserPreferences -->|Context| Agent
    TeamInfo -->|Context| Agent
    DelegationHistory -->|Context| Agent
    Recommendations -->|Context| Agent

    style Agent fill:#4CAF50
    style SessionMemory fill:#FF9800
    style UserMemory fill:#FF9800
    style TeamData fill:#FF9800
```

## 9. Slack Features Architecture

```mermaid
graph TB
    subgraph "Slack Commands"
        MyTasks[/my-tasks]
        MyPRs[/my-prs]
        Standup[/standup]
        Blockers[/blockers]
        TeamStatus[/team-status]
        Suggestions[/suggestions]
        MyWeek[/my-week]
    end

    subgraph "Feature Functions"
        GetIssues[get_user_jira_issues]
        GetPRs[get_user_prs]
        GenerateStandup[generate_standup_summary]
        GetBlockers[get_blockers]
        GetWorkload[get_team_workload]
        GetSuggestions[get_context_suggestions]
        GetWeek[get_user_calendar_events_and_tasks]
    end

    subgraph "Data Sources"
        JiraAPI[Jira API]
        GitHubAPI[GitHub API]
        CalendarAPI[Calendar API]
    end

    subgraph "Response Formatting"
        FormatText[Format Text Response]
        FormatBlocks[Format Block Kit]
        ActionButtons[Create Action Buttons]
    end

    MyTasks --> GetIssues
    MyPRs --> GetPRs
    Standup --> GenerateStandup
    Blockers --> GetBlockers
    TeamStatus --> GetWorkload
    Suggestions --> GetSuggestions
    MyWeek --> GetWeek

    GetIssues --> JiraAPI
    GetPRs --> GitHubAPI
    GenerateStandup --> JiraAPI
    GenerateStandup --> GitHubAPI
    GenerateStandup --> CalendarAPI
    GetBlockers --> JiraAPI
    GetWorkload --> JiraAPI
    GetSuggestions --> JiraAPI
    GetSuggestions --> GitHubAPI
    GetWeek --> CalendarAPI
    GetWeek --> JiraAPI

    GetIssues --> FormatText
    GetPRs --> FormatText
    GenerateStandup --> FormatText
    GetBlockers --> FormatText
    GetWorkload --> FormatText
    GetSuggestions --> FormatText
    GetWeek --> FormatText

    FormatText --> ActionButtons
    ActionButtons --> FormatBlocks
    FormatBlocks --> SlackResponse[Slack Response]

    style GetIssues fill:#4CAF50
    style GetPRs fill:#4CAF50
    style GenerateStandup fill:#FF9800
    style FormatBlocks fill:#2196F3
```

## 10. Deployment Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        SlackClient[Slack Workspace]
        CursorIDE[Cursor IDE<br/>MCP Client]
    end

    subgraph "Network Layer"
        Internet[Internet]
        Cloudflare[Cloudflare Tunnel<br/>Optional]
    end

    subgraph "EC2 Instance"
        Nginx[Nginx<br/>Reverse Proxy]
        FastAPIApp[FastAPI App<br/>Port 3000]
        MCPServer[MCP Server<br/>Port 8000]
        Systemd[Systemd Service]
    end

    subgraph "Application Services"
        SlackBot[Slack Bot Service]
        Scheduler[Scheduler Service]
        WebhookHandler[Webhook Handler]
    end

    subgraph "External APIs"
        JiraAPI[Jira Cloud]
        GitHubAPI[GitHub]
        CalendarAPI[Google Calendar]
    end

    subgraph "Database"
        MongoDB[(MongoDB<br/>Atlas or Local)]
    end

    SlackClient -->|HTTPS| Internet
    CursorIDE -->|HTTPS| Internet
    Internet -->|HTTPS| Cloudflare
    Cloudflare -->|HTTP| Nginx

    Nginx -->|Proxy| FastAPIApp
    Nginx -->|Proxy| MCPServer

    Systemd -->|Manage| FastAPIApp
    Systemd -->|Manage| MCPServer

    FastAPIApp --> SlackBot
    FastAPIApp --> Scheduler
    FastAPIApp --> WebhookHandler

    SlackBot -->|HTTP| JiraAPI
    SlackBot -->|HTTP| GitHubAPI
    SlackBot -->|HTTP| CalendarAPI
    WebhookHandler -->|HTTP| JiraAPI
    WebhookHandler -->|HTTP| GitHubAPI

    SlackBot -->|Connection| MongoDB
    Scheduler -->|Connection| MongoDB

    style FastAPIApp fill:#9C27B0
    style MCPServer fill:#2196F3
    style MongoDB fill:#FF9800
    style Systemd fill:#4CAF50
```

## 11. Error Handling Flow

```mermaid
flowchart TD
    Start([Request Received]) --> TryProcess[Try Process Request]

    TryProcess --> CheckError{Error Occurred?}

    CheckError -->|No| Success[Success Response]
    CheckError -->|Yes| ErrorType{Error Type?}

    ErrorType -->|API Error| HandleAPI[Handle API Error]
    ErrorType -->|Tool Error| HandleTool[Handle Tool Error]
    ErrorType -->|Agent Error| HandleAgent[Handle Agent Error]
    ErrorType -->|Network Error| HandleNetwork[Handle Network Error]
    ErrorType -->|Validation Error| HandleValidation[Handle Validation Error]

    HandleAPI --> CheckRetry{Retryable?}
    HandleTool --> CheckRetry
    HandleNetwork --> CheckRetry

    CheckRetry -->|Yes| Retry[Retry with Backoff]
    CheckRetry -->|No| LogError[Log Error]

    Retry --> CheckMaxRetries{Max Retries?}
    CheckMaxRetries -->|No| TryProcess
    CheckMaxRetries -->|Yes| LogError

    HandleAgent --> Fallback[Fallback to Alternative Agent]
    Fallback --> TryProcess

    HandleValidation --> UserError[Return User-Friendly Error]

    LogError --> ErrorResponse[Error Response]
    UserError --> ErrorResponse

    ErrorResponse --> NotifySlack[Notify User in Slack]
    Success --> NotifySlack

    NotifySlack --> End([End])

    style ErrorResponse fill:#F44336
    style Fallback fill:#FF9800
    style Success fill:#4CAF50
```

## 12. Tool Integration Pattern

```mermaid
graph TB
    subgraph "Tool Definition"
        ToolFunction[Async Tool Function<br/>app/tools/*.py]
        PydanticModel[Pydantic Model]
    end

    subgraph "Tool Wrapper"
        AgnoWrapper[Agno Tool Wrapper<br/>app/agno_tools/*.py]
        SyncWrapper[Synchronous Wrapper<br/>asyncio.run]
    end

    subgraph "Agent Registration"
        ToolList[Tool List]
        AgentConfig[Agent Configuration]
    end

    subgraph "Tool Execution"
        AgentCall[Agent Calls Tool]
        ToolExecution[Tool Executes]
        APIRequest[API Request]
        APIResponse[API Response]
    end

    ToolFunction --> PydanticModel
    PydanticModel --> AgnoWrapper
    AgnoWrapper --> SyncWrapper
    SyncWrapper --> ToolList
    ToolList --> AgentConfig

    AgentCall --> ToolExecution
    ToolExecution --> SyncWrapper
    SyncWrapper --> ToolFunction
    ToolFunction --> APIRequest
    APIRequest --> APIResponse
    APIResponse --> PydanticModel
    PydanticModel --> AgentCall

    style ToolFunction fill:#2196F3
    style AgnoWrapper fill:#4CAF50
    style AgentConfig fill:#FF9800
```

---

## How to Use These Diagrams

1. **View in Markdown**: Most modern Markdown viewers (GitHub, GitLab, VS Code with extensions) will render Mermaid diagrams.

2. **Online Editor**: Use [Mermaid Live Editor](https://mermaid.live) to view and edit these diagrams.

3. **VS Code Extension**: Install the "Markdown Preview Mermaid Support" extension to view diagrams in VS Code.

4. **Documentation**: These diagrams can be embedded in documentation sites that support Mermaid (e.g., MkDocs, Docusaurus).

5. **Export**: Use Mermaid CLI or online tools to export as PNG/SVG for presentations.

---

## Diagram Updates

When updating the system architecture, remember to update the relevant diagrams:

- **System Architecture**: When adding new components or services
- **Request Processing Flow**: When changing request handling logic
- **Agent Routing Logic**: When modifying routing rules
- **Tool Integration Pattern**: When adding new tools or changing tool structure
