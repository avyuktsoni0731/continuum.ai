
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

def test_memory_setup():
    print("Checking AgnoAgent configuration...")
    try:
        from app.agno_agent import AgnoAgent
        
        import inspect
        source = inspect.getsource(AgnoAgent.__init__)
        
        if "MongoDb(" in source:
             print("   [OK] MongoDb usage found in AgnoAgent code")
        else:
             print("   [FAIL] MongoDb usage NOT found in AgnoAgent code")

        if "enable_user_memories=True" in source:
             print("   [OK] enable_user_memories=True found in AgnoAgent code")
        else:
             print("   [FAIL] enable_user_memories=True NOT found in AgnoAgent code")
             
        run_source = inspect.getsource(AgnoAgent.run)
        if "user_id" in run_source:
             print("   [OK] user_id parameter found in run method")
        else:
             print("   [FAIL] user_id parameter NOT found in run method")

    except Exception as e:
        print(f"   [FAIL] Failed to load AgnoAgent: {e}")

if __name__ == "__main__":
    test_memory_setup()
