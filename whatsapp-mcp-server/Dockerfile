# The MCP server is not a service. main.py runs mcp.run(transport='stdio'), so
# it talks JSON-RPC over stdin/stdout and is spawned per-session by the MCP
# client (Claude Desktop, Claude Code). This image is therefore meant to be run
# as `docker run -i --rm ...` from a client config — not brought up by compose.
# See the Docker section of the README.
#
# ffmpeg is included because send_audio_message converts non-Opus input to the
# .ogg Opus format WhatsApp requires for playable voice messages.

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Resolve dependencies from the lockfile before copying sources, so edits to the
# server do not invalidate the dependency layer. --frozen fails loudly rather
# than silently re-resolving if uv.lock is out of date.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

# whatsapp.py reads the message database directly from disk and only calls the
# bridge's REST API for sends and downloads, so the container needs both the
# store volume and network access to the bridge.
ENV WHATSAPP_STORE_DIR=/data/store
ENV WHATSAPP_API_BASE_URL=http://whatsapp-bridge:8080/api

# Unbuffered, so diagnostics on stderr are not held back behind the stdio
# JSON-RPC traffic on stdout.
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["uv", "run", "--frozen", "--no-dev", "main.py"]
