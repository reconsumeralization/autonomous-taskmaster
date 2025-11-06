import asyncio
import logging
import json
import subprocess # Import subprocess
import sys # Import sys
import os # Import os
from pathlib import Path
# from mcp.client.fastmcp import FastMCPClient # Old import
# from mcp.client.sse import SSEClient # Old import
from mcp.client.sse import sse_client # Correct import for SSE transport
from mcp.client.stdio import StdioServerParameters, stdio_client # Correct import
from mcp.client.session import ClientSession # Import ClientSession

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    # --- Choose Transport ---
    # transport_type = "sse"
    transport_type = "stdio"

    if transport_type == "sse":
        # --- SSE Configuration ---
        server_url = "http://localhost:8000/messages/"
        logging.info(f"Connecting via SSE to MCP server at {server_url}...")
        client_context = sse_client(server_url)
    elif transport_type == "stdio":
        # --- Stdio Configuration ---
        # Define the command to start the server via stdio
        # Separate command and args
        server_executable = sys.executable
        server_script = "../autotype_mcp_server/src/mcp_server.py"
        server_args = ["--transport", "stdio"]
        client_script_dir = Path(__file__).resolve().parent # .../autotype_mcp_client/src
        autotype_root_dir = client_script_dir.parent.parent # .../autotype
        server_cwd = str(autotype_root_dir / "autotype_mcp_server") # Correct path
        server_params = StdioServerParameters(
            command=server_executable,
            args=[server_script] + server_args, # Combine script path and args
            cwd=server_cwd # Set the working directory for the server subprocess
        )
        logging.info(f"Connecting via stdio, starting server with: {server_params.command} {' '.join(server_params.args)} in cwd: {server_params.cwd}...")
        client_context = stdio_client(server_params) # Pass StdioServerParameters object
    else:
        logging.error(f"Unsupported transport type: {transport_type}")
        return

    try:
        # Use async with for the chosen transport client context
        async with client_context as (read, write):
            # Use async with for the session
            async with ClientSession(read, write) as session:
                # Initialize the session (negotiates capabilities)
                await session.initialize()
                logging.info("Session initialized.")

                # List available tools (or prompts, resources)
                tools = await session.list_tools()
                logging.info(f"Available tools: {tools}")

                # Check if the required tool exists
                # tool_to_call = "server_status"
                # tool_to_call = "update_project_map"
                tool_to_call = "autonomous_dev_loop_tool" # Call the main loop tool

                if tool_to_call not in tools:
                    logging.error(f"'{tool_to_call}' tool not found on the server.")
                    return

                logging.info(f"Calling '{tool_to_call}' tool...")
                # Call the tool (no parameters needed for update_project_map)
                # result = await session.call_tool_str_str("server_status", "{}") # Old call
                # result = await session.call_tool_str_str("update_project_map", "{}") 
                result = await session.call_tool_str_str(tool_to_call, "{}") # No arguments needed
                logging.info(f"Tool call result: {result}")
                
                # Parse the JSON result string
                try:
                    result_data = json.loads(result)
                    logging.info(f"Parsed result data: {result_data}")
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse tool result JSON: {e}")

    except ConnectionRefusedError:
        logging.error(f"Connection refused. Is the MCP server running at {server_url}?")
    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)
    finally:
        # ClientSession doesn't have a close method, closing handled by async with
        logging.info("Client finished.")

if __name__ == "__main__":
    # Use asyncio.run() in Python 3.7+
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Client interrupted by user.") 