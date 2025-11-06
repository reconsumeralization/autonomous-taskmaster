import asyncio
import logging
import sys
import json
from typing import Any

from mcp.client.sse import sse_client

# region Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger("MCPClient")
# endregion

# region Constants
SERVER_URL = "http://127.0.0.1:8000/sse"
# endregion

# region Utility Functions
def pretty_json(data: Any) -> str:
    try:
        return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to pretty-print JSON: {e}")
        return str(data)
# endregion

# region Core Client Logic
async def call_and_log_tool(client, tool_name: str, params: dict = None):
    logger.info(f"Calling tool: {tool_name} with params: {params or {}}")
    try:
        result = await client.call_tool(tool_name, **(params or {}))
        logger.info(f"Tool '{tool_name}' call successful. Result:\n{pretty_json(result)}")
        return result
    except Exception as e:
        logger.error(f"Error calling tool '{tool_name}': {e}", exc_info=True)
        return None

async def list_and_log_tools(client):
    logger.info("Fetching available tools from server...")
    try:
        tools = await client.list_tools()
        logger.info(f"Available tools ({len(tools)}):")
        for tool in tools:
            logger.info(f"  - {tool.get('name', str(tool))}")
        return tools
    except Exception as e:
        logger.error(f"Error listing tools: {e}", exc_info=True)
        return []
# endregion

# region Main Async Entry
async def main():
    logger.info("MCP Client starting up.")
    logger.info(f"Connecting to MCP server at {SERVER_URL} ...")
    client = None
    try:
        async with sse_client(SERVER_URL) as client:
            logger.info("Connected to MCP server.")

            # 1. List available tools
            await list_and_log_tools(client)

            # 2. Call 'list_tasks' tool and pretty-print result
            await call_and_log_tool(client, "list_tasks")

            # 3. (Optional) Demonstrate calling a non-existent tool for error handling
            # await call_and_log_tool(client, "nonexistent_tool")

            # 4. (Optional) Listen for server events/messages (if supported)
            # if hasattr(client, "listen"):
            #     logger.info("Listening for server events/messages...")
            #     async for event in client.listen():
            #         logger.info(f"Received event: {event}")

            # 5. Keep connection open for demonstration
            await asyncio.sleep(2)
            logger.info("Demo complete, closing connection.")

    except ConnectionRefusedError:
        logger.error(f"Connection refused. Is the MCP server running at {SERVER_URL}?")
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
    finally:
        if client and getattr(client, "is_connected", False):
            logger.info("Disconnecting from MCP server (explicit call)...")
            await client.disconnect()
            logger.info("Disconnected from MCP server.")
        else:
            logger.info("Client was not connected or already disconnected.")
# endregion

# region Script Entrypoint
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Client interrupted by user.")
        sys.exit(0)
# endregion