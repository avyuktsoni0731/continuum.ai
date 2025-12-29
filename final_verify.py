
import os
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("memory_test")

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

def final_test():
    print("Final Verification...")
    try:
        from app.agno_agent import AgnoAgent
        
        import inspect
        source = inspect.getsource(AgnoAgent.__init__)
        
        flags = {
            "MongoDb(": False,
            "enable_user_memories=True": False,
            "get_github_pulls_tool": False,  # Check for new tools
            "list_calendars_tool": False     # Check for new tools
        }
        
        for flag in flags:
            if flag in source:
                flags[flag] = True
                print(f"   [OK] Found: {flag}")
            else:
                print(f"   [FAIL] Missing: {flag}")
                
        run_source = inspect.getsource(AgnoAgent.run)
        if "user_id" in run_source:
             print("   [OK] user_id parameter found in run method")
        else:
             print("   [FAIL] user_id parameter NOT found in run method")

    except Exception as e:
        print(f"   [FAIL] Error: {e}")

if __name__ == "__main__":
    final_test()
