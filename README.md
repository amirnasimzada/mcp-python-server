# Python MCP Server

A minimal custom MCP server using the official Python MCP SDK.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/server.py
```

## Build locally

```bash
docker build -t custom-python-mcp .
docker run --rm -it custom-python-mcp
```

## Publish from GitHub

Push to `main` or create a tag like `v1.0.0`.

The GitHub Actions workflow will publish to:

`ghcr.io/<OWNER>/<REPO>:latest`
