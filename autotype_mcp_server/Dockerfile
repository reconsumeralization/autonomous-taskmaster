# Dockerfile for MCP Server
FROM python:3.11-slim

# Set workdir
WORKDIR /app

# Copy requirements and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Expose the FastAPI port
EXPOSE 8080

# Default command to run the MCP server (adjust if needed)
CMD ["uvicorn", "src.mcp_server:app", "--host", "0.0.0.0", "--port", "8080"] 