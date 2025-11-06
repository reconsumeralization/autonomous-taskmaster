import sys
import os

# Add the parent directory (autotype_mcp_server) to the Python path
# This allows pytest to find the 'src' module when running from the root
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir) 