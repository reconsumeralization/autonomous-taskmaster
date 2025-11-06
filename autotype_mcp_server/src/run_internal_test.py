import logging
import json
import os
import sys
from pathlib import Path

# Ensure src directory is in path for relative imports
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

# Import config loading function and the tool function
try:
    from mcp_server import load_config, propose_plan_tool, decompose_task_tool
except ImportError as e:
    print(f"ERROR: Could not import from mcp_server: {e}")
    sys.exit(1)

# Setup logging (can keep simplified or use setup_logging if needed)
log_file = "internal_test_marker.txt"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler(log_file, mode="w", encoding="utf-8"),
                        logging.StreamHandler() # Also log to console
                    ])

# --- Test Functions --- 
def test_propose_plan(config):
    """Test the propose_plan_tool."""
    logger = logging.getLogger("InternalTest.propose_plan")
    marker = "--- INTERNAL TEST MARKER: propose_plan_tool ---"
    logger.info(marker)
    print(marker)
    try:
        test_goal = "Implement basic calculator functions (add, subtract)"
        test_context = ["config.yaml"]
        test_result = propose_plan_tool(goal=test_goal, context_files=test_context, config=config) 
        result_str = f"Internal Test Result (propose_plan):\n{json.dumps(test_result, indent=2)}"
        logger.info(result_str)
        print(result_str)
        logger.info("--- propose_plan_tool Test Complete ---")
        print("--- propose_plan_tool Test Complete ---")
    except Exception as test_err:
        logger.error(f"propose_plan_tool test failed: {test_err}", exc_info=True)
        print(f"ERROR (propose_plan): {test_err}")

def test_decompose_task(config):
    """Test the decompose_task_tool."""
    logger = logging.getLogger("InternalTest.decompose_task")
    marker = "--- INTERNAL TEST MARKER: decompose_task_tool ---"
    logger.info(marker)
    print(marker)
    try:
        test_goal = "Refactor the main utility functions into separate modules."
        # Test with project context enabled
        test_result = decompose_task_tool(goal=test_goal, use_project_context=True, config=config) 
        result_str = f"Internal Test Result (decompose_task):\n{json.dumps(test_result, indent=2)}"
        logger.info(result_str)
        print(result_str)
        logger.info("--- decompose_task_tool Test Complete ---")
        print("--- decompose_task_tool Test Complete ---")
    except Exception as test_err:
        logger.error(f"decompose_task_tool test failed: {test_err}", exc_info=True)
        print(f"ERROR (decompose_task): {test_err}")

def run_all_tests():
    """Load config and run all defined tests."""
    log_file = "internal_test_marker.txt"
    # Setup basic config for the test file itself
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[
                            logging.FileHandler(log_file, mode="w", encoding="utf-8"),
                            logging.StreamHandler() # Also log to console
                        ])
    try:
        # Load configuration
        load_config() 
        from mcp_server import config # Import the global config AFTER loading
        if not config:
            logging.error("Config could not be loaded for the tests!")
            return # Exit if config failed to load

        # --- Run Tests ---        
        test_propose_plan(config)
        test_decompose_task(config) # Run the new test
        # Add calls to other test functions here...

    except Exception as test_err:
        logging.error(f"Internal test script failed: {test_err}", exc_info=True)
        print(f"ERROR: {test_err}") # Print error to console too
        # Write error to log file
        with open(log_file, "a", encoding="utf-8") as f: # Append error
            f.write(f"\nERROR during test script: {test_err}\n")
            import traceback
            traceback.print_exc(file=f)

if __name__ == "__main__":
    run_all_tests()