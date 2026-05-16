import sys
import os
import logging

# Add current directory to path
sys.path.append(os.getcwd())

# Setup logging to stdout
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test_init")

try:
    print("Step 1: Importing LLMService...")
    from kogniterm.core.llm_service import LLMService
    print("Step 1: Done.")

    print("Step 2: Initializing LLMService...")
    llm = LLMService()
    print("Step 2: Done.")

    print("✅ Initialization successful!")
except Exception as e:
    print(f"❌ Initialization failed: {e}")
    import traceback
    traceback.print_exc()
