# DocSync Pipeline Runner
# Runs Claude Code CLI phases inside Azure Container Instances.
# Build: docker build -f docker/Dockerfile -t docsync-pipeline .
# Push:  docker tag docsync-pipeline <acr>.azurecr.io/docsync-pipeline:latest
#        docker push <acr>.azurecr.io/docsync-pipeline:latest

FROM node:20-bullseye

# ── System packages ────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        git \
        wget \
        gnupg \
        apt-transport-https \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && rm -rf /var/lib/apt/lists/*

# ── PowerShell Core (required for scripts/*.ps1) ───────────────────────────────
RUN wget -q "https://packages.microsoft.com/config/debian/11/packages-microsoft-prod.deb" \
    && dpkg -i packages-microsoft-prod.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends powershell \
    && rm -rf /var/lib/apt/lists/* packages-microsoft-prod.deb

# ── Claude Code CLI ────────────────────────────────────────────────────────────
RUN npm install -g @anthropic-ai/claude-code

# ── Entrypoint ─────────────────────────────────────────────────────────────────
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /workspace

ENTRYPOINT ["/entrypoint.sh"]
