FROM python:3.10-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy requirements and install dependencies
COPY requirements.txt .
RUN uv pip install -r requirements.txt

# Copy the application
COPY . .

# Install the package in development mode
RUN uv pip install -e .

# Expose the default SSE port
EXPOSE 3434

# Set the default command (can be overridden)
CMD ["uv", "run", "-m", "ticktick_mcp.cli", "run", "--transport", "sse", "--host", "0.0.0.0", "--port", "3434"]