# Minimal image so Glama can start the server and run MCP introspection.
# Tool listing works without a live API key (tools are declared at import time),
# so the introspection check passes; real calls need DEEPSEEK_API_KEY at runtime.
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY deepseek_mcp.py .
# MCP stdio server
CMD ["python", "deepseek_mcp.py"]
