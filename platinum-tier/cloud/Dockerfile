FROM python:3.13-slim

LABEL maintainer="AI Employee Platinum Tier"
LABEL description="Cloud AI Employee Agent — runs 24/7"

# System dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 24 LTS
RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y nodejs

# Install Claude Code
RUN npm install -g @anthropic/claude-code

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install MCP server dependencies
COPY mcp-servers/ ./mcp-servers/
RUN npm install --prefix mcp-servers/email-mcp
RUN npm install --prefix mcp-servers/social-mcp
RUN npm install --prefix mcp-servers/odoo-mcp

# Copy application code
COPY . .

# Vault mount point
VOLUME ["/vault"]

ENV VAULT_PATH=/vault
ENV DRY_RUN=false
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD python -c "from pathlib import Path; exit(0 if Path('/vault/Dashboard.md').exists() else 1)"

CMD ["python", "cloud/cloud_agent.py"]
