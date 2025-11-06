# Autotype MCP Client

This is a Python client for connecting to the `autotyper-taskmaster-mcp` server using the Model Context Protocol (MCP) over Server-Sent Events (SSE).  
It demonstrates how to establish a session, list available tools, and call server-side functions such as `update_project_map`.  
Intended for use as a reference or starting point for integrating with MCP-enabled servers.

- Requires Python 3.8+.
- See `src/autotype_mcp_client/client.py` for usage examples.
- Make sure the MCP server is running and accessible at the configured URL before starting the client.