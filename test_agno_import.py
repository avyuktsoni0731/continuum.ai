#!/usr/bin/env python3
"""Test script to verify Agno imports on EC2."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

print("Testing Agno imports...")
print(f"Python path: {sys.executable}")
print(f"Project root: {project_root}")

try:
    print("\n1. Testing agno.agent import...")
    from agno.agent import Agent
    print("   ✓ agno.agent imported successfully")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n2. Testing agno.models.google import...")
    from agno.models.google import Gemini
    print("   ✓ agno.models.google imported successfully")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n3. Testing Jira tools import...")
    from app.agno_tools.jira_tools import (
        get_jira_issues_tool,
        get_jira_issue_tool,
        get_jira_projects_tool,
        get_jira_boards_tool,
        get_jira_board_issues_tool,
        find_jira_user_tool,
        create_jira_issue_tool,
        update_jira_issue_tool
    )
    print("   ✓ All Jira tools imported successfully")
except Exception as e:
    print(f"   ✗ Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✓ All imports successful! Agno is ready to use.")

